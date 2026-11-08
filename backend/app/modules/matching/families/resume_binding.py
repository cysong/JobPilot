"""Suggest and bind a role family per resume (docs/job_matching_v3_design.md §4.4)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matching.families.classifier import Gateway, TitleToClassify, classify_titles
from app.modules.matching.families.models import JobTitleFamily, TitleFamilyStatus
from app.modules.matching.families.normalize import normalize_title
from app.modules.matching.families.registry import RoleFamilyRegistry, get_registry
from app.modules.resumes.models import Resume


@dataclass(frozen=True)
class ResumeFamilySuggestion:
    resume_id: str
    user_id: int
    title: str
    target_job_titles: tuple[str, ...]
    current: str | None
    current_source: str | None
    suggested: str | None


def suggest_family(target_job_titles: Sequence[str], cache: Mapping[str, str | None]) -> str | None:
    """Most common family among the target titles; ties go to the earliest title.

    ``cache`` maps title_key -> role family (None for ambiguous/unknown).
    """
    families = [cache.get(normalize_title(t)) for t in target_job_titles]
    families = [f for f in families if f]
    if not families:
        return None
    counts = Counter(families)
    best = max(counts.values())
    return next(f for f in families if counts[f] == best)


async def suggest_resume_families(
    db: AsyncSession, gateway: Gateway, *, user_id: int | None = None,
    registry: RoleFamilyRegistry | None = None,
) -> list[ResumeFamilySuggestion]:
    registry = registry or get_registry()
    stmt = select(Resume).where(Resume.is_draft.is_(False), Resume.is_deleted.is_(False))
    if user_id is not None:
        stmt = stmt.where(Resume.user_id == user_id)
    resumes = (await db.execute(stmt.order_by(Resume.user_id, Resume.created_at))).scalars().all()

    titles = {normalize_title(t): t for r in resumes for t in (r.target_job_titles or []) if t}
    cached = {
        row.title_key: row
        for row in (await db.execute(
            select(JobTitleFamily).where(JobTitleFamily.title_key.in_(list(titles)))
        )).scalars()
    }
    missing = [TitleToClassify(k, v) for k, v in titles.items() if k not in cached]
    if missing:
        await classify_titles(db, gateway, missing, registry=registry)
        cached = {
            row.title_key: row
            for row in (await db.execute(
                select(JobTitleFamily).where(JobTitleFamily.title_key.in_(list(titles)))
            )).scalars()
        }
    cache = {
        k: (row.role_family if row.status == TitleFamilyStatus.CLASSIFIED else None)
        for k, row in cached.items()
    }
    return [
        ResumeFamilySuggestion(
            resume_id=r.id, user_id=r.user_id, title=r.title,
            target_job_titles=tuple(r.target_job_titles or ()),
            current=r.role_family, current_source=r.role_family_source,
            suggested=suggest_family(r.target_job_titles or [], cache),
        )
        for r in resumes
    ]


async def bind_resume_family(
    db: AsyncSession, resume_id: str, role_family: str, *, source: str,
    registry: RoleFamilyRegistry | None = None,
) -> Resume:
    registry = registry or get_registry()
    if not registry.is_valid(role_family):
        raise ValueError(f"unknown role family {role_family!r}")
    if source not in ("auto", "user"):
        raise ValueError("source must be 'auto' or 'user'")
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise ValueError(f"resume {resume_id} not found")
    resume.role_family = role_family
    resume.role_family_source = source
    resume.role_family_version = registry.version
    return resume
