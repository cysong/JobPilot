"""Build and freeze an evaluation dataset (docs/job_matching_v3_design.md §8.2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application, ApplicationStatusHistory
from app.modules.jobs.models import SeekJob
from app.modules.matching.evaluation.models import ItemKind, MatchEvalDataset, MatchEvalItem
from app.modules.matching.families.classifier import Gateway, classify_missing_titles, register_jobs, resolve_pending_jobs
from app.modules.matching.families.models import JobFamilyStatus, JobRoleFamily
from app.modules.matching.families.registry import get_registry
from app.modules.matching.judge.service import load_job_context, load_user_context, plan_match
from app.modules.matching.labels.models import MatchLabel
from app.modules.resumes.models import Document, Resume
from app.shared.utils import generate_id

INTERVIEW_STATUSES = {"PHONE_SCREEN", "INTERVIEWING", "OFFER"}
EXCLUDED_STATUSES = {"FAILED"}


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    user_id: int
    random_n: int = 300
    filtered_sample: int = 80
    seed: str = "jobpilot-v3"


def _status_name(status: Any) -> str:
    return getattr(status, "value", str(status))


async def create_dataset(
    db: AsyncSession, gateway: Gateway, spec: DatasetSpec, *, created_by: int | None = None,
) -> MatchEvalDataset:
    registry = get_registry()
    items: dict[int, dict[str, Any]] = {}

    apps = (await db.execute(
        select(Application.id, Application.job_id, Application.status, Application.source_resume_id)
        .where(Application.user_id == spec.user_id, Application.is_deleted.is_(False))
    )).all()
    applied_job_ids = {job_id for _, job_id, _, _ in apps}  # includes FAILED: never sample as random
    # "Interviewed" means the application ever reached an interview stage, even if it was
    # rejected afterwards, so the status history is checked as well as the current status.
    ever_interviewed = set((await db.execute(
        select(ApplicationStatusHistory.application_id)
        .join(Application, Application.id == ApplicationStatusHistory.application_id)
        .where(Application.user_id == spec.user_id)
        .where(func.cast(ApplicationStatusHistory.to_status, String).in_(INTERVIEW_STATUSES))
    )).scalars())
    for app_id, job_id, status, resume_id in apps:
        name = _status_name(status)
        if name in EXCLUDED_STATUSES:
            continue
        reached_interview = name in INTERVIEW_STATUSES or app_id in ever_interviewed
        kind = ItemKind.INTERVIEWED if reached_interview else ItemKind.APPLIED
        if job_id in items and items[job_id]["item_kind"] == ItemKind.INTERVIEWED:
            continue
        items[job_id] = {"item_kind": kind, "applied_resume_id": resume_id, "source_id": app_id, "label": None}

    labels = (await db.execute(
        select(MatchLabel).where(MatchLabel.user_id == spec.user_id, MatchLabel.superseded_by.is_(None))
    )).scalars().all()
    for label in labels:
        entry = items.setdefault(label.job_id, {"item_kind": ItemKind.LABELED, "applied_resume_id": None,
                                                "source_id": label.id, "label": None})
        entry["label"] = label.label

    # Random jobs are sampled from the same listing period as the user's applications.
    period = (await db.execute(
        select(func.min(SeekJob.listed_at), func.max(SeekJob.listed_at)).where(SeekJob.id.in_(list(items)))
    )).one() if items else (None, None)

    random_ids: list[int] = []
    if spec.random_n and period[0] is not None:
        random_ids = list((await db.execute(
            select(SeekJob.id)
            .where(SeekJob.listed_at.between(period[0], period[1]),
                   SeekJob.id.notin_(list(set(items) | applied_job_ids)))
            .order_by(func.md5(func.concat(spec.seed, SeekJob.id)))
            .limit(spec.random_n)
        )).scalars())
        for job_id in random_ids:
            items[job_id] = {"item_kind": ItemKind.RANDOM, "applied_resume_id": None, "source_id": None, "label": None}

    # Every dataset job needs a role family before planning.
    jobs = (await db.execute(select(SeekJob.id, SeekJob.title).where(SeekJob.id.in_(list(items))))).all()
    await register_jobs(db, [(j.id, j.title) for j in jobs])
    await db.commit()
    await classify_missing_titles(db, gateway, registry=registry)
    await resolve_pending_jobs(db, gateway, registry=registry)

    families = dict((await db.execute(
        select(JobRoleFamily.job_id, JobRoleFamily.role_family)
        .where(JobRoleFamily.job_id.in_(list(items)), JobRoleFamily.status == JobFamilyStatus.CLASSIFIED)
    )).all())

    user = await load_user_context(db, spec.user_id)
    filtered_picked = 0
    for job_id in random_ids:
        if filtered_picked >= spec.filtered_sample:
            break
        family = families.get(job_id)
        if family is None:
            continue
        plan = plan_match(job_family=family, user=user, job=await load_job_context(db, job_id), registry=registry)
        if plan.prefilter == "filtered":
            items[job_id]["item_kind"] = ItemKind.RANDOM_FILTERED
            filtered_picked += 1

    resumes = (await db.execute(
        select(Resume.id, Resume.document_id, Resume.role_family, Document.content_hash)
        .join(Document, Document.id == Resume.document_id)
        .where(Resume.user_id == spec.user_id, Resume.is_draft.is_(False), Resume.is_deleted.is_(False))
    )).all()

    version = (await db.execute(
        select(func.coalesce(func.max(MatchEvalDataset.version), 0)).where(MatchEvalDataset.name == spec.name)
    )).scalar_one() + 1

    dataset = MatchEvalDataset(
        id=generate_id("med"),
        name=spec.name,
        version=version,
        config={
            "user_id": spec.user_id,
            "seed": spec.seed,
            "random_n": spec.random_n,
            "filtered_sample": spec.filtered_sample,
            "period": [p.isoformat() if isinstance(p, datetime) else None for p in period],
            "families_version": registry.version,
            "resumes": {
                r.id: {"document_id": r.document_id, "content_hash": r.content_hash, "role_family": r.role_family}
                for r in resumes
            },
            "counts": {kind: sum(1 for v in items.values() if v["item_kind"] == kind)
                       for kind in (ItemKind.INTERVIEWED, ItemKind.APPLIED, ItemKind.RANDOM,
                                    ItemKind.RANDOM_FILTERED, ItemKind.LABELED)},
            "unclassified_jobs": sorted(set(items) - set(families)),
        },
        item_count=len(items),
        created_by=created_by,
    )
    db.add(dataset)
    await db.flush()
    db.add_all(
        MatchEvalItem(dataset_id=dataset.id, user_id=spec.user_id, job_id=job_id, **entry)
        for job_id, entry in items.items()
    )
    await db.commit()
    return dataset


async def get_dataset(db: AsyncSession, ref: str) -> MatchEvalDataset:
    """Resolve ``name@vN`` / ``name@N`` / dataset id."""
    if "@" in ref:
        name, version = ref.split("@", 1)
        version = int(version.lstrip("v"))
        dataset = (await db.execute(
            select(MatchEvalDataset).where(MatchEvalDataset.name == name, MatchEvalDataset.version == version)
        )).scalar_one_or_none()
    else:
        dataset = await db.get(MatchEvalDataset, ref)
    if dataset is None:
        raise ValueError(f"dataset {ref!r} not found")
    return dataset
