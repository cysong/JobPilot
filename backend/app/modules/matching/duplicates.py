"""Reposts of the same job in another city or on another platform.

A job is a duplicate of an earlier listing when (calibration on prod data, 2026-11-11):
- the normalized titles are equal and so are the seniority words (title keys drop them),
- the listings are at most ``WINDOW_DAYS`` apart, and
- the descriptions are near-identical: max(Jaccard, containment) of 5-word shingles is at
  least 0.90 when the company names match, 0.95 when they do not (platforms name the same
  employer differently: "Kainga Ora" / "Kāinga Ora - Homes and Communities", "datacom1").

Same-title pairs split cleanly: 1,317 pairs scored >= 0.9, 392 scored < 0.9 and those were
different roles (or crowd platforms that rewrite every post). Containment catches one
platform truncating the text or adding boilerplate. Titles that differ are never grouped:
crowd platforms post one description under many unrelated titles.

The duplicate points at the group's first listing (``job_role_families.duplicate_of``);
a group never chains.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Sequence

from app.modules.matching.employment import company_key
from app.modules.matching.families.normalize import strip_accents

WINDOW_DAYS = 30
SHINGLE_WORDS = 5
SIMILARITY_SAME_COMPANY = 0.90
SIMILARITY_OTHER_COMPANY = 0.95
MIN_SHINGLES = 20  # descriptions shorter than ~25 words are not compared

_SENIORITY_ALIASES = {
    "senior": "senior", "snr": "senior", "sr": "senior", "junior": "junior", "jnr": "junior",
    "jr": "junior", "intermediate": "intermediate", "mid": "intermediate", "midlevel": "intermediate",
    "graduate": "graduate", "grad": "graduate", "intern": "intern", "internship": "intern",
    "lead": "lead", "principal": "principal", "staff": "staff", "associate": "associate",
    "head": "head", "chief": "chief", "director": "director", "manager": "manager",
}


def seniority_words(title: str | None) -> frozenset[str]:
    tokens = re.findall(r"[a-z]+", strip_accents(title or "").lower())
    return frozenset(_SENIORITY_ALIASES[t] for t in tokens if t in _SENIORITY_ALIASES)


def shingles(text: str | None) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", strip_accents(text or "").lower())
    if len(words) < SHINGLE_WORDS:
        return frozenset()
    return frozenset(" ".join(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1))


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    """max(Jaccard, containment of the shorter text in the longer)."""
    if not a or not b:
        return 0.0
    common = len(a & b)
    return max(common / len(a | b), common / min(len(a), len(b)))


def same_company(a: str | None, b: str | None) -> bool:
    ka, kb = company_key(a), company_key(b)
    if not ka or not kb:
        return False
    return ka == kb or ka.startswith(kb + " ") or kb.startswith(ka + " ")


@dataclass
class Listing:
    job_id: int
    title_key: str
    title: str
    companies: tuple[str | None, ...]
    listed_at: datetime | None
    text: str
    duplicate_of: int | None = None
    _shingles: frozenset[str] | None = field(default=None, repr=False)

    @property
    def shingles(self) -> frozenset[str]:
        if self._shingles is None:
            self._shingles = shingles(self.text)
        return self._shingles


def _companies_match(a: Listing, b: Listing) -> bool:
    return any(same_company(x, y) for x in a.companies for y in b.companies)


def is_duplicate(job: Listing, earlier: Listing) -> bool:
    if job.title_key != earlier.title_key or not job.title_key:
        return False
    if seniority_words(job.title) != seniority_words(earlier.title):
        return False
    if job.listed_at and earlier.listed_at and abs(job.listed_at - earlier.listed_at) > timedelta(days=WINDOW_DAYS):
        return False
    a, b = job.shingles, earlier.shingles
    if len(a) < MIN_SHINGLES or len(b) < MIN_SHINGLES:
        return False
    threshold = SIMILARITY_SAME_COMPANY if _companies_match(job, earlier) else SIMILARITY_OTHER_COMPANY
    return similarity(a, b) >= threshold


def assign_duplicates(new: Sequence[Listing], existing: Iterable[Listing]) -> dict[int, int]:
    """Point each new listing at the first listing of its group, if any.

    ``existing`` are listings already grouped (canonical ones have duplicate_of None).
    New listings are taken oldest first, so an earlier new listing can become the
    canonical one for a later one. Returns {job_id: canonical job_id} for new duplicates.
    """
    canonicals: dict[str, list[Listing]] = {}
    for listing in existing:
        if listing.duplicate_of is None:
            canonicals.setdefault(listing.title_key, []).append(listing)
    found: dict[int, int] = {}
    ordered = sorted(new, key=lambda j: (j.listed_at is None, j.listed_at or datetime.max, j.job_id))
    for job in ordered:
        candidates = sorted(canonicals.get(job.title_key, ()),
                            key=lambda c: (c.listed_at is None, c.listed_at or datetime.max, c.job_id))
        match = next((c for c in candidates if c.job_id != job.job_id and is_duplicate(job, c)), None)
        if match is not None:
            job.duplicate_of = match.job_id
            found[job.job_id] = match.job_id
        else:
            canonicals.setdefault(job.title_key, []).append(job)
    return found


# ------------------------------------------------------------------ database

TIER_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}


async def mark_duplicates(db, job_ids: Sequence[int]) -> int:
    """Set job_role_families.duplicate_of for ``job_ids`` (rows without one yet).

    Compares each job with the group leaders sharing its title key within the window.
    Does not commit. Returns the number of jobs marked.
    """
    from sqlalchemy import and_, select, update

    from app.modules.jobs.models import SeekJob
    from app.modules.matching.families.models import JobRoleFamily
    from app.modules.matching.text import html_to_text

    if not job_ids:
        return 0

    def listing(row) -> Listing:
        return Listing(job_id=row.job_id, title_key=row.title_key, title=row.title,
                       companies=(row.advertiser_name, row.company_name), listed_at=row.listed_at,
                       text=html_to_text(row.content) or (row.abstract or ""), duplicate_of=row.duplicate_of)

    columns = (JobRoleFamily.job_id, JobRoleFamily.title_key, JobRoleFamily.duplicate_of, SeekJob.title,
               SeekJob.advertiser_name, SeekJob.company_name, SeekJob.listed_at, SeekJob.content, SeekJob.abstract)
    new_rows = (await db.execute(
        select(*columns).join(SeekJob, SeekJob.id == JobRoleFamily.job_id)
        .where(JobRoleFamily.job_id.in_(list(job_ids)), JobRoleFamily.duplicate_of.is_(None))
    )).all()
    if not new_rows:
        return 0
    new = [listing(r) for r in new_rows]
    dates = [j.listed_at for j in new if j.listed_at]
    window = timedelta(days=WINDOW_DAYS)
    conditions = [JobRoleFamily.title_key.in_({j.title_key for j in new}),
                  JobRoleFamily.duplicate_of.is_(None), JobRoleFamily.job_id.notin_(list(job_ids))]
    if dates:
        conditions.append(SeekJob.listed_at.between(min(dates) - window, max(dates) + window))
    existing = [listing(r) for r in (await db.execute(
        select(*columns).join(SeekJob, SeekJob.id == JobRoleFamily.job_id).where(and_(*conditions))
    )).all()]
    found = assign_duplicates(new, existing)
    for job_id, leader in found.items():
        await db.execute(update(JobRoleFamily).where(JobRoleFamily.job_id == job_id).values(duplicate_of=leader))
    return len(found)


async def group_job_ids(db, job_id: int) -> list[int]:
    """All jobs in ``job_id``'s duplicate group (just [job_id] when it has none)."""
    from sqlalchemy import or_, select

    from app.modules.matching.families.models import JobRoleFamily

    leader = (await db.execute(
        select(JobRoleFamily.duplicate_of).where(JobRoleFamily.job_id == job_id)
    )).scalar_one_or_none() or job_id
    members = (await db.execute(
        select(JobRoleFamily.job_id).where(or_(JobRoleFamily.job_id == leader, JobRoleFamily.duplicate_of == leader))
    )).scalars().all()
    return sorted(set(members) | {job_id, leader})


async def judged_sibling(db, *, user_id: int, job_id: int, exclude_match_id: str):
    """The user's best judged result for another listing of the same job, if any.

    Prefers results that are not themselves merged into another one, then the best tier.
    Location rejections are per listing and never reused.
    """
    from sqlalchemy import select

    from app.modules.matching.models import JobMatch, JobMatchStatus, RejectCode

    group = await group_job_ids(db, job_id)
    if len(group) < 2:
        return None
    rows = (await db.execute(
        select(JobMatch).where(
            JobMatch.user_id == user_id, JobMatch.job_id.in_(group), JobMatch.id != exclude_match_id,
            JobMatch.status.in_([JobMatchStatus.RATED, JobMatchStatus.REJECTED]),
            JobMatch.reject_code.is_distinct_from(RejectCode.LOCATION),
        )
    )).scalars().all()
    if not rows:
        return None
    return min(rows, key=best_result_key)


def best_result_key(match) -> tuple:
    """Sort key: not merged elsewhere, rated before rejected, best tier, judged first."""
    from app.modules.matching.models import JobMatchStatus

    judged = match.judged_at.timestamp() if match.judged_at else float("inf")
    return (match.duplicate_of is not None, match.status != JobMatchStatus.RATED,
            TIER_RANK.get(match.tier or "", 9), judged, match.id)
