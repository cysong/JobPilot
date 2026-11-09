"""Load inputs, plan and run one match judgment (docs/job_matching_v3_design.md §5-§6).

Shared by the evaluation runner (stage 1) and the online queue worker (stage 2).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol, Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import availability
from app.core.llm.types import ModelOverride
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.matching.families.registry import RoleFamilyRegistry, get_registry
from app.modules.matching.judge.input_builder import (
    CandidateConditions,
    CandidateResume,
    JobInput,
    SkillLibraryEntry,
    build_judge_input,
    skill_library_supplement,
    skill_line,
    work_history_years,
)
from app.modules.matching.judge.validator import JudgeOutcome, JudgmentStructureError, validate_judgment
from app.modules.matching.location import LocationCheck, check_location
from app.modules.matching.prefilter import ResumeRef, is_job_active, select_candidates
from app.modules.matching.text import html_to_text
from app.modules.resumes.models import Document, Resume, ResumeSkill
from app.modules.users.models import UserSkill

logger = structlog.get_logger()

MATCH_JUDGE_AGENT = "match_judge"
MAX_STRUCTURE_RETRIES = 2


class Gateway(Protocol):
    async def call(self, agent_id: str, input_data: str, context: dict | None = None,
                   model_override: ModelOverride | None = None) -> Any: ...


@dataclass(frozen=True)
class UserContext:
    user_id: int
    job_locations: tuple[str, ...]
    conditions: CandidateConditions
    resumes: tuple[CandidateResume, ...]
    resume_refs: tuple[ResumeRef, ...]
    skills: tuple[SkillLibraryEntry, ...]


@dataclass(frozen=True)
class JobContext:
    job: JobInput
    location_city: str | None
    is_expired: bool | None
    manual_expired: bool | None
    expires_at: datetime | None
    company: str | None


@dataclass(frozen=True)
class MatchPlan:
    prefilter: str  # same | adjacent | filtered | location_rejected
    candidate_ids: tuple[str, ...]
    location: LocationCheck


class JudgeFailure(Exception):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


# ------------------------------------------------------------------ loading


async def load_user_context(db: AsyncSession, user_id: int) -> UserContext:
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")
    prefs = user.preferences or {}

    rows = (await db.execute(
        select(Resume, Document.content)
        .join(Document, Document.id == Resume.document_id)
        .where(Resume.user_id == user_id, Resume.is_draft.is_(False), Resume.is_deleted.is_(False))
    )).all()
    resumes = tuple(
        CandidateResume(
            id=r.id,
            title=r.title,
            role_family=r.role_family,
            content=content or "",
            work_experiences=tuple((r.analysis_result or {}).get("work_experiences") or ()),
        )
        for r, content in rows
    )
    refs = tuple(ResumeRef(id=r.id, role_family=r.role_family, updated_at=r.updated_at) for r, _ in rows)
    skills = await _load_skill_library(db, user_id)
    return UserContext(
        user_id=user_id,
        job_locations=tuple(prefs.get("job_locations") or ()),
        conditions=CandidateConditions(
            work_rights=prefs.get("work_rights"),
            security_clearance=prefs.get("security_clearance"),
            # The platform targets NZ: a user without a stated country is treated as NZ-based.
            country=prefs.get("country") or settings.MATCH_DEFAULT_COUNTRY,
            languages=tuple(prefs.get("languages") or ()),
        ),
        resumes=resumes,
        resume_refs=refs,
        skills=skills,
    )


async def _load_skill_library(db: AsyncSession, user_id: int) -> tuple[SkillLibraryEntry, ...]:
    user_skills = (await db.execute(select(UserSkill).where(UserSkill.user_id == user_id))).scalars().all()
    evidence: dict[str, list[str]] = {}
    for name, extracted in (await db.execute(
        select(ResumeSkill.skill_name, ResumeSkill.extracted_from).where(ResumeSkill.user_id == user_id)
    )).all():
        for source in extracted or []:
            if isinstance(source, dict):
                for quote in source.get("quotes") or []:
                    evidence.setdefault(name.lower(), []).append(str(quote))
    entries = []
    for skill in user_skills:
        level = skill.manual_proficiency if skill.is_manual and skill.manual_proficiency else skill.proficiency_level
        entries.append(SkillLibraryEntry(
            skill_name=skill.skill_name,
            proficiency=getattr(level, "value", str(level)),
            evidence=tuple(evidence.get(skill.skill_name.lower(), ())),
        ))
    return tuple(entries)


async def load_job_context(db: AsyncSession, job_id: int) -> JobContext:
    job = await db.get(SeekJob, job_id)
    if job is None:
        raise ValueError(f"job {job_id} not found")
    description = html_to_text(job.content) or (job.abstract or "")
    return JobContext(
        job=JobInput(
            id=job.id,
            title=job.title,
            location_label=job.location_label,
            work_types_label=job.work_types_label,
            listed_at=job.listed_at,
            description=description,
        ),
        location_city=job.location_city,
        is_expired=job.is_expired,
        manual_expired=job.manual_expired,
        expires_at=job.expires_at,
        company=job.advertiser_name or job.company_name,
    )


def job_is_active(ctx: JobContext, *, now: datetime | None = None) -> bool:
    return is_job_active(
        is_expired=ctx.is_expired,
        manual_expired=ctx.manual_expired,
        expires_at=ctx.expires_at,
        listed_at=ctx.job.listed_at,
        now=now or datetime.now(timezone.utc),
        expiry_days=settings.JOB_EXPIRY_DAYS,
    )


# ------------------------------------------------------------------ planning


def plan_match(
    *, job_family: str, user: UserContext, job: JobContext, registry: RoleFamilyRegistry | None = None,
) -> MatchPlan:
    """Prefilter and location filter for one job x user (no LLM)."""
    registry = registry or get_registry()
    selection = select_candidates(
        job_family=job_family,
        resumes=user.resume_refs,
        registry=registry,
        max_candidates=settings.MATCH_MAX_CANDIDATE_RESUMES,
    )
    location = check_location(
        user_locations=user.job_locations,
        location_city=job.location_city,
        location_label=job.job.location_label,
        work_types_label=job.job.work_types_label,
        title=job.job.title,
    )
    if selection is None:
        return MatchPlan("filtered", (), location)
    if location.status == "rejected":
        return MatchPlan("location_rejected", selection.resume_ids, location)
    return MatchPlan(selection.relation, selection.resume_ids, location)


def fallback_candidates(user: UserContext) -> tuple[str, ...]:
    """Most recently updated resumes bound to a family, used to judge prefilter-filtered
    samples in evaluation. Resumes without a family are excluded from matching."""
    refs = sorted((r for r in user.resume_refs if r.role_family), key=lambda r: r.updated_at, reverse=True)
    return tuple(r.id for r in refs[: settings.MATCH_MAX_CANDIDATE_RESUMES])


# ------------------------------------------------------------------ judging


def judge_override() -> ModelOverride:
    return ModelOverride(provider=settings.MATCH_LLM_PROVIDER, model=settings.MATCH_JUDGE_MODEL)


async def judge_pair(
    gateway: Gateway,
    *,
    user: UserContext,
    job: JobContext,
    candidate_ids: Sequence[str],
    model_override: ModelOverride | None = None,
    context: dict | None = None,
    today: date | None = None,
) -> tuple[JudgeOutcome, dict]:
    """Call match_judge and validate. Returns (outcome, gateway context).

    Structural output problems are retried up to MAX_STRUCTURE_RETRIES times;
    gateway errors are surfaced as retryable ``JudgeFailure``.
    """
    by_id = {r.id: r for r in user.resumes}
    resumes = [by_id[i] for i in candidate_ids if i in by_id]
    if not resumes:
        raise JudgeFailure("no candidate resumes", retryable=False)
    extra_skills = skill_library_supplement(user.skills, resumes)
    prompt = build_judge_input(conditions=user.conditions, resumes=resumes, extra_skills=extra_skills, job=job.job)
    today = today or date.today()
    history = {r.id: work_history_years(r.work_experiences, today) for r in resumes}
    override = model_override or judge_override()

    last_error: Exception | None = None
    for attempt in range(MAX_STRUCTURE_RETRIES + 1):
        call_context = dict(context or {})
        call_context.setdefault("operation", "match_judge")
        call_context.setdefault("user_id", user.user_id)
        try:
            raw = await gateway.call(MATCH_JUDGE_AGENT, prompt, context=call_context, model_override=override)
        except Exception as exc:  # noqa: BLE001
            if availability.is_unavailable(exc):
                raise  # LLM work is paused: not a judging failure
            raise JudgeFailure(f"gateway error: {exc}", retryable=True) from exc
        try:
            outcome = validate_judgment(
                raw,
                candidate_ids=[r.id for r in resumes],
                job_text=job.job.description,
                resume_texts={r.id: r.content for r in resumes},
                skill_texts=[skill_line(s) for s in extra_skills],
                conditions=user.conditions,
                history_years=history,
            )
        except JudgmentStructureError as exc:
            last_error = exc
            logger.warning("match_judge_structure_error", attempt=attempt, error=str(exc))
            continue
        outcome.validation["structure_retries"] = attempt
        return outcome, call_context
    raise JudgeFailure(f"invalid output after retries: {last_error}", retryable=False)
