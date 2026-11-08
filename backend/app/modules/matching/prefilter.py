"""Prefilter rules for matching v3 (docs/job_matching_v3_design.md §5.1). Pure functions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from app.modules.matching.families.registry import FamilyRelation, RoleFamilyRegistry


@dataclass(frozen=True)
class ResumeRef:
    id: str
    role_family: str | None
    updated_at: datetime


@dataclass(frozen=True)
class CandidateSelection:
    relation: FamilyRelation
    resume_ids: tuple[str, ...]


def is_job_active(
    *,
    is_expired: bool | None,
    manual_expired: bool | None,
    expires_at: datetime | None,
    listed_at: datetime | None,
    now: datetime,
    expiry_days: int,
) -> bool:
    """A job is live unless flagged expired, past expires_at, or (without
    expires_at) listed more than ``expiry_days`` ago."""
    if is_expired or manual_expired:
        return False
    if expires_at is not None:
        return expires_at > now
    if listed_at is None:
        return False
    return listed_at > now - timedelta(days=expiry_days)


def select_candidates(
    *,
    job_family: str,
    resumes: Sequence[ResumeRef],
    registry: RoleFamilyRegistry,
    max_candidates: int,
) -> CandidateSelection | None:
    """Pick a user's candidate resumes for a job: same family first, else adjacent.

    Resumes without a family never qualify. When more than ``max_candidates``
    qualify, the most recently updated ones are kept.
    """
    same = [r for r in resumes if r.role_family == job_family]
    if same:
        relation: FamilyRelation = "same"
        chosen = same
    else:
        adjacent = registry.adjacent(job_family)
        chosen = [r for r in resumes if r.role_family in adjacent]
        relation = "adjacent"
    if not chosen:
        return None
    chosen = sorted(chosen, key=lambda r: r.updated_at, reverse=True)[:max_candidates]
    return CandidateSelection(relation=relation, resume_ids=tuple(r.id for r in chosen))
