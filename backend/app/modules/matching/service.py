"""Read and manage matching v3 results for the API (docs/job_matching_v3_design.md §7-§8)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.applications.models import Application
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.jobs.repository import JobRepository, UserJobViewRepository
from app.modules.jobs.schemas import JobBriefInfo, ResumeBriefInfo
from app.modules.matching.families.classifier import refresh_job_families, set_title_family
from app.modules.matching.families.models import JobRoleFamily, JobTitleFamily
from app.modules.matching.families.normalize import normalize_title
from app.modules.matching.families.registry import get_registry
from app.modules.matching.labels.models import MatchLabel
from app.modules.matching.labels.service import add_label, current_labels
from app.modules.matching.models import JobMatch, JobMatchStatus
from app.modules.matching.pipeline import active_job_clause
from app.modules.matching.schemas import (
    MatchCounts,
    MatchDetail,
    MatchLabelCreate,
    MatchLabelInfo,
    MatchListItem,
    MatchListResponse,
    MatchSummary,
    ResumeRoleFamilyResponse,
    RoleFamilyInfo,
    TitleFamilyItem,
    TitleFamilyListResponse,
    TitleFamilyUpdateResponse,
)
from app.modules.resumes.models import Resume
from app.shared.enums import Role

DEFAULT_TIERS = ("A", "B")
USER_TIERS = ("A", "B", "C")  # D is kept for evaluation and never shown to users
PENDING_STATUSES = (JobMatchStatus.QUEUED, JobMatchStatus.FAILED_RETRYABLE)


def _is_admin(user: User) -> bool:
    return user.role == Role.ADMIN


def _allowed_tiers(user: User, tiers: Sequence[str] | None) -> tuple[str, ...]:
    allowed = ("A", "B", "C", "D") if _is_admin(user) else USER_TIERS
    chosen = tuple(t for t in (tiers or DEFAULT_TIERS) if t in allowed)
    if not chosen:
        raise BadRequestError(f"tiers must be among {', '.join(allowed)}")
    return chosen


async def _application_status_map(db: AsyncSession, user_id: int, job_ids: list[int]) -> dict[int, str]:
    if not job_ids:
        return {}
    rows = (await db.execute(
        select(Application.job_id, Application.status)
        .where(Application.user_id == user_id, Application.is_deleted.is_(False), Application.job_id.in_(job_ids))
        .order_by(Application.created_at)
    )).all()
    return {job_id: getattr(status, "value", str(status)) for job_id, status in rows}


async def _counts(db: AsyncSession, user_id: int, now: datetime) -> MatchCounts:
    rows = (await db.execute(
        select(JobMatch.status, JobMatch.tier, func.count())
        .join(SeekJob, SeekJob.id == JobMatch.job_id)
        .where(JobMatch.user_id == user_id, active_job_clause(now))
        .group_by(JobMatch.status, JobMatch.tier)
    )).all()
    counts = MatchCounts()
    for status, tier, count in rows:
        if status == JobMatchStatus.RATED and tier in USER_TIERS:
            setattr(counts, tier, getattr(counts, tier) + count)
        elif status == JobMatchStatus.REJECTED:
            counts.rejected += count
        elif status in PENDING_STATUSES:
            counts.pending += count
    return counts


def _summary(match: JobMatch, resume: Resume | None, application_status: str | None,
             label: MatchLabel | None) -> dict:
    return {
        "id": match.id, "status": match.status, "tier": match.tier, "tier_reason": match.tier_reason,
        "tech_level": match.tech_level, "experience_level": match.experience_level,
        "family_relation": match.family_relation, "location_check": match.location_check,
        "reject_code": match.reject_code, "reject_reason": match.reject_reason,
        "reject_quote": match.reject_quote, "judged_at": match.judged_at,
        "recommended_resume": ResumeBriefInfo.model_validate(resume) if resume else None,
        "application_status": application_status,
        "label": MatchLabelInfo.model_validate(label) if label else None,
    }


async def list_matches(
    db: AsyncSession, user: User, *, view: str = "recommended", tiers: Sequence[str] | None = None,
    limit: int = 20, offset: int = 0, now: datetime | None = None,
) -> MatchListResponse:
    """Live jobs with a result for this user, newest first.

    recommended: rated jobs in the chosen tiers (default A+B). rejected: jobs rejected
    by a hard condition, with the reason and the JD quote.
    """
    now = now or datetime.now(timezone.utc)
    stmt = (
        select(JobMatch)
        .join(SeekJob, SeekJob.id == JobMatch.job_id)
        .where(JobMatch.user_id == user.id, active_job_clause(now))
    )
    if view == "rejected":
        stmt = stmt.where(JobMatch.status == JobMatchStatus.REJECTED)
    else:
        stmt = stmt.where(JobMatch.status == JobMatchStatus.RATED, JobMatch.tier.in_(_allowed_tiers(user, tiers)))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    matches = list((await db.execute(
        stmt.order_by(SeekJob.listed_at.desc().nullslast(), JobMatch.id).limit(limit).offset(offset)
    )).scalars())

    job_ids = [m.job_id for m in matches]
    job_map = await JobRepository.get_brief_map(db, job_ids)
    view_map = await UserJobViewRepository.get_view_map(db=db, user_id=user.id, job_ids=job_ids)
    applications = await _application_status_map(db, user.id, job_ids)
    resumes = await _resume_map(db, [m.resume_id for m in matches if m.resume_id])
    labels = await current_labels(db, user_id=user.id, job_ids=job_ids) if _is_admin(user) else {}

    items = []
    for match in matches:
        job = job_map.get(match.job_id)
        if job is None:
            continue
        info = JobBriefInfo.model_validate(job)
        viewed = view_map.get(match.job_id)
        info.is_viewed = viewed is not None
        info.last_viewed_at = viewed.last_viewed_at if viewed else None
        info.has_application = match.job_id in applications
        items.append(MatchListItem(job=info, match=MatchSummary(**_summary(
            match, resumes.get(match.resume_id), applications.get(match.job_id), labels.get(match.job_id)))))
    return MatchListResponse(items=items, total=total, counts=await _counts(db, user.id, now))


async def _resume_map(db: AsyncSession, resume_ids: list[str]) -> dict[str, Resume]:
    if not resume_ids:
        return {}
    rows = (await db.execute(select(Resume).where(Resume.id.in_(set(resume_ids))))).scalars()
    return {r.id: r for r in rows}


async def get_match_detail(db: AsyncSession, user: User, job_id: int) -> MatchDetail | None:
    match = (await db.execute(
        select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job_id)
    )).scalar_one_or_none()
    if match is None or (match.tier == "D" and not _is_admin(user)):
        return None
    resume = await db.get(Resume, match.resume_id) if match.resume_id else None
    applications = await _application_status_map(db, user.id, [job_id])
    label = (await current_labels(db, user_id=user.id, job_ids=[job_id])).get(job_id) if _is_admin(user) else None
    judgment = match.judgment or {}
    return MatchDetail(
        **_summary(match, resume, applications.get(job_id), label),
        job_id=job_id,
        tech_items=judgment.get("tech_items") or [],
        relevant_years=judgment.get("relevant_years"),
        required_years=judgment.get("required_years"),
        experience_evidence=judgment.get("experience_evidence") or [],
        work_rights=judgment.get("work_rights"),
        security_clearance=judgment.get("security_clearance"),
        work_location=judgment.get("work_location"),
        languages=judgment.get("languages"),
        other_constraints=judgment.get("other_constraints") or [],
        seniority_mismatch=judgment.get("seniority_mismatch"),
        is_different_track=judgment.get("is_different_track"),
        model=match.model,
        prompt_version=match.prompt_version,
    )


# ------------------------------------------------------------------ role families


def list_role_families() -> list[RoleFamilyInfo]:
    registry = get_registry()
    return [RoleFamilyInfo(key=f.key, label=f.label, label_zh=f.label_zh, description=f.description)
            for f in (registry.get(k) for k in registry.keys)]


async def set_resume_role_family(
    db: AsyncSession, user: User, resume_id: str, role_family: str | None,
) -> ResumeRoleFamilyResponse:
    """Bind (or unbind with None) a resume's family as the user's choice.

    Existing matches are not re-judged; the next pipeline run plans live jobs that
    have no result yet against the new binding (backfill).
    """
    resume = await db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id or resume.is_deleted:
        raise NotFoundError("Resume not found")
    registry = get_registry()
    if role_family is not None and not registry.is_valid(role_family):
        raise BadRequestError(f"Unknown role family: {role_family}")
    resume.role_family = role_family
    resume.role_family_source = "user"
    resume.role_family_version = registry.version if role_family else None
    resume.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return ResumeRoleFamilyResponse(resume_id=resume.id, role_family=resume.role_family,
                                    role_family_source=resume.role_family_source)


# ------------------------------------------------------------------ admin


async def create_label(db: AsyncSession, admin: User, payload: MatchLabelCreate) -> MatchLabelInfo:
    """Stage 2: admins label their own matches, including jobs without a result
    ("should have matched")."""
    if await db.get(SeekJob, payload.job_id) is None:
        raise NotFoundError("Job not found")
    try:
        row = await add_label(db, user_id=admin.id, job_id=payload.job_id, label=payload.label,
                              labeled_by=admin.id, source="ui", reason_tags=payload.reason_tags, note=payload.note)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    await db.commit()
    return MatchLabelInfo.model_validate(row)


async def _job_counts(db: AsyncSession, keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    return dict((await db.execute(
        select(JobRoleFamily.title_key, func.count()).where(JobRoleFamily.title_key.in_(keys))
        .group_by(JobRoleFamily.title_key)
    )).all())


def _title_item(row: JobTitleFamily, job_count: int) -> TitleFamilyItem:
    return TitleFamilyItem(title_key=row.title_key, example_title=row.example_title, status=row.status,
                           role_family=row.role_family, source=row.source, families_version=row.families_version,
                           job_count=job_count, updated_at=row.updated_at)


async def list_title_families(
    db: AsyncSession, *, q: str | None = None, role_family: str | None = None, status: str | None = None,
    limit: int = 50, offset: int = 0,
) -> TitleFamilyListResponse:
    stmt = select(JobTitleFamily)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(JobTitleFamily.title_key.like(pattern),
                              func.lower(JobTitleFamily.example_title).like(pattern)))
    if role_family:
        stmt = stmt.where(JobTitleFamily.role_family == role_family)
    if status:
        stmt = stmt.where(JobTitleFamily.status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = list((await db.execute(stmt.order_by(JobTitleFamily.title_key).limit(limit).offset(offset))).scalars())
    counts = await _job_counts(db, [r.title_key for r in rows])
    return TitleFamilyListResponse(items=[_title_item(r, counts.get(r.title_key, 0)) for r in rows], total=total)


async def update_title_family(
    db: AsyncSession, admin: User, title: str, role_family: str | None,
) -> TitleFamilyUpdateResponse:
    """Pin a title to a family (or to ambiguous) and re-derive its jobs' families.

    Jobs sent back to pending get a JD read on the next pipeline run. Existing match
    results are kept (no re-judging).
    """
    if not normalize_title(title):
        raise BadRequestError("Title is empty after normalization")
    try:
        row = await set_title_family(db, title, role_family, updated_by=admin.id)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    await db.commit()
    job_ids = list((await db.execute(
        select(JobRoleFamily.job_id).where(JobRoleFamily.title_key == row.title_key)
    )).scalars())
    counts = await refresh_job_families(db, job_ids) if job_ids else {"changed": 0, "to_pending": 0}
    await db.refresh(row)
    return TitleFamilyUpdateResponse(item=_title_item(row, len(job_ids)), jobs_changed=counts["changed"],
                                     jobs_to_pending=counts["to_pending"])
