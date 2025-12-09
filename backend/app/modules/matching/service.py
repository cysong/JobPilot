"""Matching logic between jobs and users."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import JobAnalysis, SeekJob
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.users.repository import UserSkillRepository
from app.shared.enums import ProficiencyLevel


def _proficiency_weight(value: str) -> float:
    mapping = {
        ProficiencyLevel.EXPERT.value: 1.0,
        ProficiencyLevel.ADVANCED.value: 0.9,
        ProficiencyLevel.INTERMEDIATE.value: 0.7,
        ProficiencyLevel.BEGINNER.value: 0.4,
    }
    return mapping.get(value, 0.0)


def _average_or_zero(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def calculate_skill_match_score(
    *,
    user_skills: list[dict],
    job_analysis: JobAnalysis,
    required_weight: float = 0.7,
    preferred_weight: float = 0.2,
    soft_weight: float = 0.1,
) -> tuple[float, dict]:
    """Compute weighted skill match score."""
    # Build lookup by lower name
    skill_lookup = {s["skill_name"].lower(): s for s in user_skills}

    required_scores = []
    for name in job_analysis.required_skills:
        hit = skill_lookup.get(name.lower())
        required_scores.append(_proficiency_weight(hit["proficiency"]) if hit else 0.0)

    preferred_scores = []
    for name in job_analysis.preferred_skills:
        hit = skill_lookup.get(name.lower())
        preferred_scores.append(_proficiency_weight(hit["proficiency"]) if hit else 0.0)

    soft_scores = []
    for name in job_analysis.soft_skills:
        hit = skill_lookup.get(name.lower())
        if hit and hit.get("skill_type") == "soft":
            soft_scores.append(1.0)
        else:
            soft_scores.append(0.0)

    required_component = _average_or_zero(required_scores) * required_weight * 100
    preferred_component = _average_or_zero(preferred_scores) * preferred_weight * 100
    soft_component = _average_or_zero(soft_scores) * soft_weight * 100

    total = required_component + preferred_component + soft_component

    details = {
        "required_component": required_component,
        "preferred_component": preferred_component,
        "soft_component": soft_component,
        "required_skills_scored": required_scores,
        "preferred_skills_scored": preferred_scores,
        "soft_skills_scored": soft_scores,
    }
    return total, details


def calculate_resume_match_score(
    *,
    resume_analysis: dict,
    job_analysis: JobAnalysis,
) -> tuple[float, dict]:
    """Reuse skill matching against resume_analysis technical and soft skills."""
    resume_technical = resume_analysis.get("technical_skills", [])
    resume_soft = resume_analysis.get("soft_skills", [])

    # Normalize into user_skills-like structure
    normalized_skills = []
    for skill in resume_technical:
        normalized_skills.append(
            {
                "skill_name": skill.get("name", ""),
                "proficiency": skill.get("proficiency", ""),
                "skill_type": "technical",
            }
        )
    for skill_name in resume_soft:
        normalized_skills.append(
            {"skill_name": skill_name, "proficiency": ProficiencyLevel.INTERMEDIATE.value, "skill_type": "soft"}
        )

    return calculate_skill_match_score(user_skills=normalized_skills, job_analysis=job_analysis)


async def prefilter_candidates_by_title(
    db: AsyncSession,
    *,
    normalized_job_title: str,
    max_candidates: int,
) -> list[int]:
    """Find user_ids whose formal resumes include the normalized title in target_job_titles."""
    stmt = text(
        """
        SELECT DISTINCT r.user_id
        FROM resumes r
        WHERE r.is_draft = FALSE
          AND r.is_deleted = FALSE
          AND r.analysis_result IS NOT NULL
          AND LOWER(:title) = ANY (
              SELECT LOWER(elem::text)::text
              FROM jsonb_array_elements_text(r.analysis_result->'target_job_titles') AS elem
          )
        LIMIT :max_candidates
        """
    )
    result = await db.execute(stmt, {"title": normalized_job_title, "max_candidates": max_candidates})
    return [row[0] for row in result.fetchall()]


async def find_best_resume_for_user(
    db: AsyncSession,
    *,
    user_id: int,
    job_analysis: JobAnalysis,
) -> tuple[Optional[str], float, dict]:
    """Pick best formal resume with analysis for this user."""
    q = text(
        """
        SELECT id, title, analysis_result
        FROM resumes
        WHERE user_id = :user_id
          AND is_draft = FALSE
          AND is_deleted = FALSE
          AND analysis_result IS NOT NULL
        """
    )
    result = await db.execute(q, {"user_id": user_id})
    rows = result.fetchall()
    best_id: Optional[str] = None
    best_score = 0.0
    best_details: dict = {}

    for row in rows:
        resume_id, title, analysis_json = row
        score, details = calculate_resume_match_score(resume_analysis=analysis_json, job_analysis=job_analysis)
        if score > best_score:
            best_score = score
            best_id = resume_id
            best_details = {
                "resume_title": title,
                "score_breakdown": details,
                "total_experience_years": analysis_json.get("total_experience_years"),
                "target_job_titles": analysis_json.get("target_job_titles", []),
            }
    return best_id, best_score, best_details


async def get_recent_job_analyses(db: AsyncSession, *, hours: int = 24) -> list[JobAnalysis]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return await JobAnalysisRepository.get_updated_since(db, since=since)


async def get_recent_jobs_with_analysis(db: AsyncSession, *, days: int = 30) -> list[JobAnalysis]:
    """Jobs listed in last N days that already have analysis."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(JobAnalysis)
        .join(SeekJob, SeekJob.id == JobAnalysis.job_id)
        .where(SeekJob.listed_at >= cutoff)
        .order_by(JobAnalysis.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def user_has_title_target(db: AsyncSession, *, user_id: int, normalized_job_title: str) -> bool:
    """Check if user has a formal resume whose target_job_titles contains the title (case-insensitive)."""
    stmt = text(
        """
        SELECT 1
        FROM resumes r
        WHERE r.user_id = :user_id
          AND r.is_draft = FALSE
          AND r.is_deleted = FALSE
          AND r.analysis_result IS NOT NULL
          AND LOWER(:title) = ANY (
              SELECT LOWER(elem::text)::text
              FROM jsonb_array_elements_text(r.analysis_result->'target_job_titles') AS elem
          )
        LIMIT 1
        """
    )
    result = await db.execute(stmt, {"user_id": user_id, "title": normalized_job_title})
    return result.first() is not None
