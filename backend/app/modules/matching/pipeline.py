"""Online matching pipeline (docs/job_matching_v3_design.md §10).

discover_new_jobs  -> register live jobs that have no role family row yet
enqueue_matches    -> for every user with a family-bound resume, plan each classified live
                      job without a match row: queue it, store a LOCATION rejection, or
                      skip it (prefilter). Covers new jobs and backfill alike: a resume that
                      gets (re)bound makes previously skipped jobs plannable on the next run.
judge_queued_matches -> claim queued / due retry rows (newest jobs first), judge them and
                      store the outcome; ``job_matches`` itself is the task ledger.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import structlog
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import availability
from app.core.metrics import match_judge_duration_seconds, match_judge_total, match_validation_total
from app.modules.jobs.models import SeekJob
from app.modules.matching.families.classifier import register_jobs
from app.modules.matching.families.models import JobFamilyStatus, JobRoleFamily
from app.modules.matching.families.registry import RoleFamilyRegistry, get_registry
from app.modules.matching.judge.input_builder import JobInput
from app.modules.matching.judge.service import (
    Gateway,
    JobContext,
    JudgeFailure,
    UserContext,
    job_is_active,
    judge_override,
    judge_pair,
    load_job_context,
    load_user_context,
    plan_match,
)
from app.modules.matching.models import JobMatch, JobMatchStatus, RejectCode
from app.modules.matching.text import sha256_hex
from app.modules.resumes.models import Resume
from app.shared.utils import generate_id

logger = structlog.get_logger()

SessionFactory = Callable[[], Any]

ORIGIN_NEW_JOB = "new_job"
ORIGIN_BACKFILL = "backfill"


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def active_job_clause(now: datetime):
    """SQL form of prefilter.is_job_active."""
    return and_(
        SeekJob.is_expired.is_not(True),
        SeekJob.manual_expired.is_not(True),
        or_(
            SeekJob.expires_at > now,
            and_(SeekJob.expires_at.is_(None),
                 SeekJob.listed_at > now - timedelta(days=settings.JOB_EXPIRY_DAYS)),
        ),
    )


# ------------------------------------------------------------------ discover


async def discover_new_jobs(db: AsyncSession, *, now: datetime | None = None, limit: int | None = None) -> int:
    """Register live jobs without a job_role_families row (newest first)."""
    now = _now(now)
    rows = (await db.execute(
        select(SeekJob.id, SeekJob.title)
        .where(active_job_clause(now),
               ~exists().where(JobRoleFamily.job_id == SeekJob.id))
        .order_by(SeekJob.listed_at.desc().nullslast())
        .limit(limit or settings.MATCH_DISCOVER_LIMIT)
    )).all()
    added = await register_jobs(db, [(r.id, r.title) for r in rows])
    await db.commit()
    return added


# ------------------------------------------------------------------ enqueue


async def matching_user_ids(db: AsyncSession) -> list[int]:
    """Users with at least one formal resume bound to a role family."""
    return list((await db.execute(
        select(Resume.user_id).where(Resume.role_family.is_not(None), Resume.is_draft.is_(False),
                                     Resume.is_deleted.is_(False)).distinct()
    )).scalars())


async def enqueue_matches(
    db: AsyncSession, *, now: datetime | None = None, registry: RoleFamilyRegistry | None = None,
    user_ids: list[int] | None = None,
) -> dict[str, int]:
    """Plan every classified live job that has no match row for a matching user."""
    now = _now(now)
    registry = registry or get_registry()
    counts = {"queued": 0, "location_rejected": 0, "filtered": 0}
    for user_id in user_ids if user_ids is not None else await matching_user_ids(db):
        user = await load_user_context(db, user_id)
        bound = [r for r in user.resume_refs if r.role_family]
        if not bound:
            continue
        # Jobs classified after the latest resume change are new; older ones are backfill.
        bound_at = max(r.updated_at for r in bound)
        jobs = (await db.execute(
            select(JobRoleFamily.job_id, JobRoleFamily.role_family, JobRoleFamily.families_version,
                   JobRoleFamily.updated_at, SeekJob.title, SeekJob.location_city, SeekJob.location_label,
                   SeekJob.work_types_label, SeekJob.listed_at)
            .join(SeekJob, SeekJob.id == JobRoleFamily.job_id)
            .where(JobRoleFamily.status == JobFamilyStatus.CLASSIFIED, active_job_clause(now),
                   ~exists().where(JobMatch.user_id == user_id, JobMatch.job_id == JobRoleFamily.job_id))
        )).all()
        rows = []
        for job in jobs:
            ctx = JobContext(
                job=JobInput(id=job.job_id, title=job.title, location_label=job.location_label,
                             work_types_label=job.work_types_label, listed_at=job.listed_at, description=""),
                location_city=job.location_city, is_expired=None, manual_expired=None, expires_at=None,
                company=None,
            )
            plan = plan_match(job_family=job.role_family, user=user, job=ctx, registry=registry)
            if plan.prefilter == "filtered":
                counts["filtered"] += 1
                continue
            row = {
                "id": generate_id("jm"),
                "user_id": user_id,
                "job_id": job.job_id,
                "origin": ORIGIN_NEW_JOB if job.updated_at >= bound_at else ORIGIN_BACKFILL,
                "job_family": job.role_family,
                "families_version": job.families_version or registry.version,
                "candidate_resume_ids": list(plan.candidate_ids),
                "location_check": plan.location.status,
                "job_listed_at": job.listed_at,
                # Multi-row inserts take their columns from the first row: keep keys uniform.
                "reject_code": None,
                "reject_reason": None,
            }
            if plan.prefilter == "location_rejected":
                # No LLM call: the city is outside the user's preferences.
                row.update(status=JobMatchStatus.REJECTED, family_relation=_relation(user, job.role_family),
                           reject_code=RejectCode.LOCATION,
                           reject_reason="Job location is outside your preferred locations.")
                counts["location_rejected"] += 1
            else:
                row.update(status=JobMatchStatus.QUEUED, family_relation=plan.prefilter)
                counts["queued"] += 1
            rows.append(row)
        for start in range(0, len(rows), 500):
            await db.execute(pg_insert(JobMatch).values(rows[start:start + 500])
                             .on_conflict_do_nothing(index_elements=[JobMatch.user_id, JobMatch.job_id]))
        await db.commit()
    return counts


def _relation(user: UserContext, job_family: str) -> str:
    # Mirrors prefilter.select_candidates: same family wins over adjacent.
    return "same" if any(r.role_family == job_family for r in user.resume_refs) else "adjacent"


# ------------------------------------------------------------------ judge


@dataclass
class JudgeRunStats:
    claimed: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)
    limited_users: set[int] = field(default_factory=set)

    def add(self, outcome: str) -> None:
        self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {"claimed": self.claimed, **self.outcomes, "limited_users": sorted(self.limited_users)}


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def _claim(db: AsyncSession, now: datetime, size: int, stats: JudgeRunStats) -> list[str]:
    """Lease up to ``size`` due rows, respecting each user's daily LLM limit.

    The lease (next_attempt_at in the future) keeps overlapping runs from taking the
    same rows; a crashed run's rows become due again when the lease ends.
    """
    used = dict((await db.execute(
        # Every finished attempt counts, failed ones included (they may still be billed).
        select(JobMatch.user_id, func.count()).where(JobMatch.judged_at >= _day_start(now))
        .group_by(JobMatch.user_id)
    )).all())
    due = (await db.execute(
        select(JobMatch.id, JobMatch.user_id)
        .where(JobMatch.status.in_([JobMatchStatus.QUEUED, JobMatchStatus.FAILED_RETRYABLE]),
               or_(JobMatch.next_attempt_at.is_(None), JobMatch.next_attempt_at <= now))
        .order_by(JobMatch.job_listed_at.desc().nullslast(), JobMatch.queued_at)
        .limit(size * 5)
        .with_for_update(skip_locked=True)
    )).all()
    chosen: list[str] = []
    for match_id, user_id in due:
        if used.get(user_id, 0) >= settings.MATCH_DAILY_LLM_LIMIT_PER_USER:
            stats.limited_users.add(user_id)
            continue
        used[user_id] = used.get(user_id, 0) + 1
        chosen.append(match_id)
        if len(chosen) == size:
            break
    if chosen:
        await db.execute(update(JobMatch).where(JobMatch.id.in_(chosen)).values(
            next_attempt_at=now + timedelta(minutes=settings.MATCH_JUDGE_LEASE_MINUTES)))
    await db.commit()
    return chosen


async def judge_queued_matches(
    session_factory: SessionFactory, gateway: Gateway, *, now: Callable[[], datetime] | None = None,
    time_budget_seconds: float | None = None,
) -> dict[str, Any]:
    """Judge due rows in chunks of MATCH_JUDGE_CONCURRENCY until the batch size or the
    time budget is used up. A chunk already started always finishes."""
    clock = now or (lambda: datetime.now(timezone.utc))
    budget = settings.MATCH_JUDGE_TIME_BUDGET_SECONDS if time_budget_seconds is None else time_budget_seconds
    concurrency = settings.MATCH_JUDGE_CONCURRENCY
    started = time.monotonic()
    stats = JudgeRunStats()
    users: dict[int, UserContext] = {}
    while stats.claimed < settings.MATCH_JUDGE_BATCH_SIZE and time.monotonic() - started < budget:
        if availability.is_paused():
            stats.add("paused")
            break
        async with session_factory() as db:
            size = min(concurrency, settings.MATCH_JUDGE_BATCH_SIZE - stats.claimed)
            ids = await _claim(db, clock(), size, stats)
        if not ids:
            break
        stats.claimed += len(ids)
        results = await asyncio.gather(
            *(_judge_one(session_factory, gateway, match_id, users, clock) for match_id in ids),
            return_exceptions=True,
        )
        for match_id, result in zip(ids, results):
            if isinstance(result, BaseException):
                # Unexpected error (DB, bug): the lease expires and the row is retried later.
                logger.error("match_judge_unexpected_error", match_id=match_id, error=str(result))
                result = "error"
            stats.add(result)
            match_judge_total.labels(outcome=result).inc()
        if "paused" in results:
            break  # LLM work paused: leave the rest queued
    return stats.as_dict()


async def _judge_one(
    session_factory: SessionFactory, gateway: Gateway, match_id: str, users: dict[int, UserContext],
    clock: Callable[[], datetime],
) -> str:
    async with session_factory() as db:
        match = await db.get(JobMatch, match_id)
        if match is None or match.status not in (JobMatchStatus.QUEUED, JobMatchStatus.FAILED_RETRYABLE):
            return "skipped"
        job = await load_job_context(db, match.job_id)
        if not job_is_active(job, now=clock()):
            match.status, match.next_attempt_at = JobMatchStatus.SKIPPED_EXPIRED, None
            await db.commit()
            return JobMatchStatus.SKIPPED_EXPIRED
        if match.user_id not in users:
            users[match.user_id] = await load_user_context(db, match.user_id)
        user = users[match.user_id]
        override = judge_override()
        match.attempts += 1
        started = time.monotonic()
        try:
            outcome, ctx = await judge_pair(
                gateway, user=user, job=job, candidate_ids=match.candidate_resume_ids, model_override=override,
                context={"operation": "match_judge", "user_id": match.user_id},
            )
        except availability.LLMUnavailableError:
            # LLM work is paused: not this pair's fault. Undo the attempt, release the lease
            # and leave the row as it was; judging resumes when credit is back.
            match.attempts -= 1
            match.next_attempt_at = None
            await db.commit()
            return "paused"
        except JudgeFailure as exc:
            match_judge_duration_seconds.observe(time.monotonic() - started)
            backoff = settings.MATCH_RETRY_BACKOFF_MINUTES
            match.error = str(exc)[:2000]
            match.judged_at = clock()
            if exc.retryable and match.attempts <= len(backoff):
                match.status = JobMatchStatus.FAILED_RETRYABLE
                match.next_attempt_at = clock() + timedelta(minutes=backoff[match.attempts - 1])
            else:
                match.status, match.next_attempt_at = JobMatchStatus.FAILED_FINAL, None
            await db.commit()
            logger.warning("match_judge_failed", match_id=match_id, status=match.status, error=match.error)
            return match.status
        match_judge_duration_seconds.observe(time.monotonic() - started)
        _count_validation(outcome.validation)
        resume = next(r for r in user.resumes if r.id == outcome.resume_id)
        match.status = outcome.status
        match.resume_id = outcome.resume_id
        match.resume_content_hash = sha256_hex(resume.content)
        match.job_content_hash = sha256_hex(job.job.description)
        match.tier = outcome.tier
        match.tier_reason = outcome.tier_reason
        match.tech_level = outcome.tech_level
        match.experience_level = outcome.experience_level
        match.reject_code = outcome.reject_code
        match.reject_reason = outcome.reject_reason
        match.reject_quote = outcome.reject_quote
        match.judgment = outcome.judgment
        match.validation = outcome.validation
        match.model = override.model
        match.prompt_version = settings.MATCH_JUDGE_PROMPT_VERSION
        match.ai_call_id = ctx.get("ai_call_id")
        match.judged_at = clock()
        match.next_attempt_at = None
        match.error = None
        await db.commit()
        return outcome.status


def _count_validation(validation: dict[str, Any]) -> None:
    for kind, value in (("consistency_fix", len(validation.get("consistency_fixes") or [])),
                        ("flag", len(validation.get("flags") or [])),
                        ("unverified_quote", int(validation.get("quotes_unverified") or 0))):
        if value:
            match_validation_total.labels(kind=kind).inc(value)
