"""Build the match_judge prompt input (docs/job_matching_v3_design.md §6.1).

Sections are ordered so that everything stable for a user (conditions, resumes,
skill library) comes before the job, which lets the provider cache the prefix
across consecutive judgments for the same user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Sequence


@dataclass(frozen=True)
class CandidateResume:
    id: str
    title: str
    role_family: str | None
    content: str
    work_experiences: Sequence[dict] = field(default_factory=tuple)


@dataclass(frozen=True)
class SkillLibraryEntry:
    skill_name: str
    proficiency: str
    evidence: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class CandidateConditions:
    work_rights: str | None
    security_clearance: str | None
    country: str = "New Zealand"
    languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobInput:
    id: int
    title: str
    location_label: str | None
    work_types_label: str | None
    listed_at: datetime | None
    description: str


MAX_SKILL_EVIDENCE = 2

# A language name and the spoken varieties a JD may ask for instead. Users write
# "Chinese" in preferences while JDs ask for "Mandarin" (calibration 2026-11-11).
_LANGUAGE_VARIETIES: dict[str, tuple[str, ...]] = {
    "chinese": ("Mandarin", "Cantonese"),
    "mandarin": ("Chinese",),
    "cantonese": ("Chinese",),
}


def describe_languages(languages: Sequence[str]) -> str:
    """'Chinese, English' -> 'Chinese (Mandarin, Cantonese), English'."""
    parts = []
    for language in languages:
        varieties = _LANGUAGE_VARIETIES.get(language.strip().lower())
        parts.append(f"{language} ({', '.join(varieties)})" if varieties else language)
    return ", ".join(parts)


def skill_library_supplement(
    skills: Iterable[SkillLibraryEntry], resumes: Sequence[CandidateResume]
) -> list[SkillLibraryEntry]:
    """Skills from the user's library that none of the candidate resumes mention."""
    corpus = "\n".join(r.content for r in resumes).lower()
    missing = []
    for skill in skills:
        name = skill.skill_name.strip()
        if not name:
            continue
        pattern = rf"(?<![\w+#.]){re.escape(name.lower())}(?![\w+#])"
        if not re.search(pattern, corpus):
            missing.append(skill)
    return sorted(missing, key=lambda s: s.skill_name.lower())


def build_judge_input(
    *,
    conditions: CandidateConditions,
    resumes: Sequence[CandidateResume],
    extra_skills: Sequence[SkillLibraryEntry],
    job: JobInput,
) -> str:
    lines: list[str] = ["[CANDIDATE CONDITIONS]"]
    lines.append(f"work_rights: {conditions.work_rights or 'unknown'}")
    lines.append(f"security_clearance: {conditions.security_clearance or 'unknown'}")
    lines.append(f"located_in: {conditions.country}")
    lines.append(f"languages: {describe_languages(conditions.languages) if conditions.languages else 'unknown'}")

    lines.append("")
    lines.append("[CANDIDATE RESUMES]")
    for resume in resumes:
        lines.append(f"=== resume_id: {resume.id}")
        lines.append(f"title: {resume.title}")
        lines.append(f"role_family: {resume.role_family or 'unknown'}")
        lines.append("content:")
        lines.append(resume.content.strip())
        lines.append(f"=== end of resume {resume.id}")

    lines.append("")
    lines.append("[ADDITIONAL SKILLS FROM SKILL LIBRARY]")
    if extra_skills:
        for skill in extra_skills:
            evidence = "; ".join(f'"{e}"' for e in list(skill.evidence)[:MAX_SKILL_EVIDENCE])
            suffix = f" evidence: {evidence}" if evidence else " evidence: (added manually)"
            lines.append(f"- {skill.skill_name} ({skill.proficiency}).{suffix}")
    else:
        lines.append("(none)")

    lines.append("")
    lines.append("[JOB]")
    lines.append(f"title: {job.title}")
    lines.append(f"location: {job.location_label or 'unknown'}")
    lines.append(f"work_type: {job.work_types_label or 'unknown'}")
    lines.append(f"listed_at: {job.listed_at.date().isoformat() if job.listed_at else 'unknown'}")
    lines.append("description:")
    lines.append(job.description.strip())
    return "\n".join(lines)


def skill_line(skill: SkillLibraryEntry) -> str:
    """The text a skill contributes to the prompt (used for quote verification)."""
    evidence = "; ".join(list(skill.evidence)[:MAX_SKILL_EVIDENCE])
    return f"{skill.skill_name} ({skill.proficiency}) {evidence}"


_MONTH = re.compile(r"^(\d{4})(?:-(\d{1,2}))?")


def _parse_month(value: str | None, today: date) -> date | None:
    if not value:
        return None
    text = value.strip().lower()
    if text in ("present", "current", "now", "ongoing"):
        return today.replace(day=1)
    match = _MONTH.match(text)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def work_history_years(work_experiences: Iterable[dict], today: date) -> float:
    """Total years covered by dated work experiences, overlapping spans merged.

    Used as an upper bound for the LLM's ``relevant_years``. Entries without a
    parsable start are ignored.
    """
    spans: list[tuple[date, date]] = []
    for exp in work_experiences or ():
        duration = exp.get("duration") or []
        start = _parse_month(duration[0] if len(duration) > 0 else None, today)
        end = _parse_month(duration[1] if len(duration) > 1 else "present", today)
        if start is None or end is None or end < start:
            continue
        spans.append((start, end))
    if not spans:
        return 0.0
    spans.sort()
    total_months = 0
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total_months += _months(cur_start, cur_end)
            cur_start, cur_end = start, end
    total_months += _months(cur_start, cur_end)
    return round(total_months / 12, 2)


def _months(start: date, end: date) -> int:
    # Inclusive of the end month: 2020-01..2020-12 is 12 months.
    return (end.year - start.year) * 12 + (end.month - start.month) + 1
