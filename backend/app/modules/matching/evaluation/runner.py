"""Run matching v3 over a frozen dataset and produce the unified report.

Never writes to job_matches. Resume content and role families come from the
dataset snapshot, so runs on the same dataset stay comparable over time.
"""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm.availability import LLMUnavailableError
from app.core.llm.types import ModelOverride
from app.modules.matching.evaluation.dataset import get_dataset
from app.modules.matching.evaluation.metrics import compare_runs, compute_metrics
from app.modules.matching.evaluation.models import ItemKind, MatchEvalItem, MatchEvalPrediction, MatchEvalRun
from app.modules.matching.evaluation.report import render_report
from app.modules.matching.families.models import JobFamilyStatus, JobRoleFamily
from app.modules.matching.families.registry import get_registry
from app.modules.matching.judge.service import (
    Gateway,
    JobContext,
    JudgeFailure,
    UserContext,
    fallback_candidates,
    judge_override,
    judge_pair,
    load_job_context,
    load_user_context,
    plan_match,
)
from app.modules.matching.prefilter import ResumeRef
from app.modules.resumes.models import Document
from app.shared.utils import generate_id

logger = structlog.get_logger()

SessionFactory = Callable[[], AsyncSession]


async def _frozen_user_context(db: AsyncSession, user_id: int, frozen: dict[str, dict]) -> UserContext:
    """User context with resume content and families as frozen in the dataset."""
    user = await load_user_context(db, user_id)
    docs = dict((await db.execute(
        select(Document.id, Document.content).where(
            Document.id.in_([v["document_id"] for v in frozen.values()])
        )
    )).all())
    resumes, refs = [], []
    by_id = {r.id: r for r in user.resumes}
    old_refs = {r.id: r for r in user.resume_refs}
    for resume_id, snap in frozen.items():
        current = by_id.get(resume_id)
        if current is None or snap["document_id"] not in docs:
            continue  # resume deleted since freezing
        resumes.append(dataclasses.replace(current, content=docs[snap["document_id"]], role_family=snap["role_family"]))
        refs.append(ResumeRef(resume_id, snap["role_family"], old_refs[resume_id].updated_at))
    return dataclasses.replace(user, resumes=tuple(resumes), resume_refs=tuple(refs))


FOCUS_LABELED = "labeled"


async def run_evaluation(
    session_factory: SessionFactory,
    gateway: Gateway,
    *,
    dataset_ref: str,
    model_override: ModelOverride | None = None,
    prompt_version: str | None = None,
    repeats: int = 1,
    concurrency: int | None = None,
    baseline_run_id: str | None = None,
    limit: int | None = None,
    judged_limit: int | None = None,
    repeat_sample: int | None = None,
    sample_seed: str = "eval",
    reuse_run_id: str | None = None,
    focus: str | None = None,
) -> MatchEvalRun:
    """Evaluate a dataset.

    ``judged_limit`` keeps only that many of the pairs that reach the LLM (others
    that would reach it are left out of the run; prefilter-only pairs stay).
    ``repeat_sample`` limits extra repeats to that many LLM pairs. Both pick
    pairs by a stable hash of (sample_seed, job_id), so smaller samples are
    subsets of larger ones.
    ``reuse_run_id`` copies successful LLM results (rated / rejected) from an
    earlier run of the same dataset and model, and only judges the rest; used to
    resume a run that stopped part-way (e.g. provider credit exhausted).
    ``focus="labeled"`` keeps only items with ground truth: a human label or an
    application that reached an interview (cheap prompt iterations).
    """
    registry = get_registry()
    override = model_override or judge_override()
    async with session_factory() as db:
        dataset = await get_dataset(db, dataset_ref)
        items = list((await db.execute(
            select(MatchEvalItem).where(MatchEvalItem.dataset_id == dataset.id).order_by(MatchEvalItem.job_id)
        )).scalars())
        if focus == FOCUS_LABELED:
            items = [i for i in items if i.label is not None or i.item_kind == ItemKind.INTERVIEWED]
        elif focus is not None:
            raise ValueError(f"unknown focus {focus!r}")
        if limit:
            items = items[:limit]
        job_ids = [i.job_id for i in items]
        families = dict((await db.execute(
            select(JobRoleFamily.job_id, JobRoleFamily.role_family).where(
                JobRoleFamily.job_id.in_(job_ids), JobRoleFamily.status == JobFamilyStatus.CLASSIFIED)
        )).all())
        method_counts = Counter((await db.execute(
            select(JobRoleFamily.method).where(JobRoleFamily.job_id.in_(job_ids))
        )).scalars())
        user_ids = {i.user_id for i in items}
        users = {uid: await _frozen_user_context(db, uid, dataset.config.get("resumes", {})) for uid in user_ids}
        jobs: dict[int, JobContext] = {jid: await load_job_context(db, jid) for jid in job_ids}

        def llm_candidates(item: MatchEvalItem, user: UserContext) -> tuple[str, ...]:
            """Resumes sent to the judge for this item; empty when it never reaches the LLM."""
            family = families.get(item.job_id)
            if family is not None:
                plan = plan_match(job_family=family, user=user, job=jobs[item.job_id], registry=registry)
                if plan.prefilter in ("same", "adjacent"):
                    return plan.candidate_ids
                if plan.prefilter == "location_rejected":
                    return ()
            if item.item_kind == ItemKind.RANDOM_FILTERED:
                return fallback_candidates(user)
            return ()

        def reaches_llm(item: MatchEvalItem) -> bool:
            return bool(llm_candidates(item, users[item.user_id]))

        def rank(item: MatchEvalItem) -> str:
            return hashlib.sha256(f"{sample_seed}:{item.job_id}".encode()).hexdigest()

        llm_items = sorted((i for i in items if reaches_llm(i)), key=rank)
        if judged_limit is not None:
            dropped = {(i.user_id, i.job_id) for i in llm_items[judged_limit:]}
            items = [i for i in items if (i.user_id, i.job_id) not in dropped]
            llm_items = llm_items[:judged_limit]
        repeat_items = llm_items if repeat_sample is None else llm_items[:repeat_sample]

        reused: dict[tuple[int, int, int], dict[str, Any]] = {}
        if reuse_run_id:
            source = await db.get(MatchEvalRun, reuse_run_id)
            if source is None:
                raise ValueError(f"run {reuse_run_id} not found")
            if source.config.get("model") != override.model:
                raise ValueError(
                    f"run {reuse_run_id} used {source.config.get('model')}, not {override.model}")
            current_prompt = prompt_version or settings.MATCH_JUDGE_PROMPT_VERSION
            if source.config.get("prompt_version") != current_prompt:
                raise ValueError(f"run {reuse_run_id} used prompt {source.config.get('prompt_version')}, "
                                 f"not {current_prompt}")
            source_users = users
            if source.dataset_id != dataset.id:
                # Another dataset version may have a different resume snapshot: rebuild it so
                # a result is only reused when the judge saw exactly the same candidates.
                source_dataset = await get_dataset(db, source.dataset_id)
                source_users = {
                    uid: await _frozen_user_context(db, uid, source_dataset.config.get("resumes", {}))
                    for uid in user_ids
                }
            by_key = {(i.user_id, i.job_id): i for i in items}
            for row in await load_run_rows(db, reuse_run_id):
                item = by_key.get((row["user_id"], row["job_id"]))
                if item is None or not row["judged"] or row["status"] not in ("rated", "rejected"):
                    continue
                now_cands = llm_candidates(item, users[item.user_id])
                then_cands = llm_candidates(item, source_users[item.user_id])
                if now_cands and set(now_cands) == set(then_cands):
                    reused[(row["user_id"], row["job_id"], row["repeat_index"])] = row

        run = MatchEvalRun(
            id=generate_id("mer"),
            dataset_id=dataset.id,
            config={
                "dataset": f"{dataset.name}@v{dataset.version}",
                "provider": override.provider,
                "model": override.model,
                "prompt_version": prompt_version or settings.MATCH_JUDGE_PROMPT_VERSION,
                "families_version": registry.version,
                "repeats": repeats,
                "items": len(items),
                "llm_pairs": len(llm_items),
                "judged_limit": judged_limit,
                "repeat_sample": len(repeat_items) if repeats > 1 else 0,
                "sample_seed": sample_seed,
                "reused_from": reuse_run_id,
                "reused_pairs": len(reused),
                "focus": focus,
            },
            baseline_run_id=baseline_run_id,
            status="running",
        )
        db.add(run)
        await db.commit()

    sem = asyncio.Semaphore(concurrency or settings.MATCH_JUDGE_CONCURRENCY)
    rows: list[dict[str, Any]] = []
    progress = {"done": 0, "total": len(llm_items) + len(repeat_items) * (repeats - 1) - len(reused)}

    async def evaluate(item: MatchEvalItem, repeat: int) -> None:
        job = jobs[item.job_id]
        user = users[item.user_id]
        family = families.get(item.job_id)
        row = {
            "user_id": item.user_id, "job_id": item.job_id, "repeat_index": repeat,
            "item_kind": item.item_kind, "label": item.label, "applied_resume_id": item.applied_resume_id,
            "title": job.job.title, "company": job.company, "family": family,
            "prefilter": "filtered", "location_check": None, "status": None, "tier": None,
            "reject_code": None, "resume_id": None, "tier_reason": None, "judged": False,
            "validation": None, "usage": [], "error": None, "judgment": None,
        }
        if family is not None:
            plan = plan_match(job_family=family, user=user, job=job, registry=registry)
            row["prefilter"], row["location_check"] = plan.prefilter, plan.location.status
            if plan.prefilter == "location_rejected":
                row["status"], row["reject_code"] = "rejected", "LOCATION"
        candidates = llm_candidates(item, user)
        previous = reused.get((item.user_id, item.job_id, repeat)) if candidates else None
        if previous is not None:
            row.update({k: previous[k] for k in (
                "status", "tier", "tier_reason", "reject_code", "resume_id", "validation", "judgment", "usage")})
            row["judged"] = True
            row["reused"] = True  # copied from an earlier run: its cost was paid there
            candidates = ()
        if candidates:
            async with sem:
                try:
                    outcome, ctx = await judge_pair(gateway, user=user, job=job, candidate_ids=candidates,
                                                    model_override=override)
                    row.update(
                        judged=True, status=outcome.status, tier=outcome.tier, tier_reason=outcome.tier_reason,
                        reject_code=outcome.reject_code, resume_id=outcome.resume_id,
                        validation=outcome.validation, judgment=outcome.judgment,
                        usage=[ctx["usage"]] if ctx.get("usage") else [],
                    )
                except (JudgeFailure, LLMUnavailableError) as exc:
                    # Paused LLM work fails the pair here; ``reuse_run_id`` resumes the run later.
                    row.update(judged=True, status="failed_final", error=str(exc)[:2000])
                    logger.warning("eval_judge_failed", job_id=item.job_id, error=str(exc))
            progress["done"] += 1
            if progress["done"] % 25 == 0 or progress["done"] == progress["total"]:
                print(f"  judged {progress['done']}/{progress['total']}", flush=True)
        rows.append(row)

    tasks = [evaluate(item, 0) for item in items]
    # Repeats only make sense for pairs that reach the LLM; planning is deterministic.
    for repeat in range(1, repeats):
        tasks.extend(evaluate(item, repeat) for item in repeat_items)
    try:
        await asyncio.gather(*tasks)
    except Exception as exc:
        async with session_factory() as db:
            failed = await db.get(MatchEvalRun, run.id)
            failed.status, failed.error = "failed", str(exc)[:2000]
            failed.finished_at = datetime.now(timezone.utc)
            await db.commit()
        raise

    family_stats = {
        "jobs": len(items),
        "classified": len(families),
        "pending": len(items) - len(families),
        "failed": 0,
        "jd_read_rate": round(method_counts.get("jd_read", 0) / len(families), 4) if families else None,
        "by_family": dict(Counter(families.values())),
    }
    metrics = compute_metrics(rows, family_stats=family_stats)

    async with session_factory() as db:
        comparison = None
        if baseline_run_id:
            comparison = compare_runs(await load_run_rows(db, baseline_run_id), rows)
        run = await db.get(MatchEvalRun, run.id)
        db.add_all(
            MatchEvalPrediction(
                run_id=run.id, repeat_index=r["repeat_index"], user_id=r["user_id"], job_id=r["job_id"],
                prefilter=r["prefilter"], location_check=r["location_check"], status=r["status"],
                tier=r["tier"], reject_code=r["reject_code"], resume_id=r["resume_id"],
                judgment={**{k: r[k] for k in ("judgment", "validation", "usage", "tier_reason", "family",
                                               "judged", "error", "title", "company")},
                          "reused": bool(r.get("reused"))},
            )
            for r in rows
        )
        run.metrics = metrics
        run.cost = metrics["cost"]
        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.report_md = render_report(run={"id": run.id, **run.config}, metrics=metrics, comparison=comparison)
        await db.commit()
        return run


async def load_run_rows(db: AsyncSession, run_id: str) -> list[dict[str, Any]]:
    """Rebuild metric rows for a stored run (used for comparisons and re-reports)."""
    run = await db.get(MatchEvalRun, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    items = {
        (i.user_id, i.job_id): i
        for i in (await db.execute(select(MatchEvalItem).where(MatchEvalItem.dataset_id == run.dataset_id))).scalars()
    }
    rows = []
    for p in (await db.execute(select(MatchEvalPrediction).where(MatchEvalPrediction.run_id == run_id))).scalars():
        item = items.get((p.user_id, p.job_id))
        extra = p.judgment or {}
        rows.append({
            "user_id": p.user_id, "job_id": p.job_id, "repeat_index": p.repeat_index,
            "item_kind": item.item_kind if item else "unknown", "label": item.label if item else None,
            "applied_resume_id": item.applied_resume_id if item else None,
            "title": extra.get("title"), "company": extra.get("company"), "family": extra.get("family"),
            "prefilter": p.prefilter, "location_check": p.location_check, "status": p.status,
            "tier": p.tier, "reject_code": p.reject_code, "resume_id": p.resume_id,
            "tier_reason": extra.get("tier_reason"), "judged": bool(extra.get("judged")),
            "validation": extra.get("validation"), "usage": extra.get("usage") or [],
            "judgment": extra.get("judgment"),
            "reused": bool(extra.get("reused")),
        })
    return rows
