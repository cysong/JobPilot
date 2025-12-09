"""Repository for user-job matches."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matching.models import UserJobMatch
from app.shared.utils import generate_id


class UserJobMatchRepository:
    """CRUD helpers for user_job_matches."""

    @staticmethod
    async def upsert(
        db: AsyncSession,
        user_id: int,
        job_id: int,
        skill_match_score: float,
        skill_match_details: dict,
        *,
        recommended_resume_id: Optional[str] = None,
        resume_match_score: Optional[float] = None,
        resume_match_details: Optional[dict] = None,
        matching_algorithm_version: str = "v1.0.0",
    ) -> UserJobMatch:
        stmt = select(UserJobMatch).where(
            and_(UserJobMatch.user_id == user_id, UserJobMatch.job_id == job_id)
        )
        result = await db.execute(stmt)
        match = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if match:
            match.skill_match_score = skill_match_score
            match.skill_match_details = skill_match_details
            match.recommended_resume_id = recommended_resume_id
            match.resume_match_score = resume_match_score
            match.resume_match_details = resume_match_details
            match.matching_algorithm_version = matching_algorithm_version
            match.calculated_at = now
            match.updated_at = now
            match.ai_match_score = None
            match.ai_analysis = None
            match.ai_analyzed_at = None
        else:
            match = UserJobMatch(
                id=generate_id("ujm"),
                user_id=user_id,
                job_id=job_id,
                skill_match_score=skill_match_score,
                skill_match_details=skill_match_details,
                recommended_resume_id=recommended_resume_id,
                resume_match_score=resume_match_score,
                resume_match_details=resume_match_details,
                matching_algorithm_version=matching_algorithm_version,
                calculated_at=now,
            )
            db.add(match)

        return match

    @staticmethod
    async def update_ai_analysis(
        db: AsyncSession,
        match_id: str,
        ai_match_score: float,
        ai_analysis: dict,
        ai_analyzed_at: datetime,
    ) -> UserJobMatch:
        stmt = select(UserJobMatch).where(UserJobMatch.id == match_id)
        result = await db.execute(stmt)
        match = result.scalar_one_or_none()

        if not match:
            raise ValueError(f"UserJobMatch {match_id} not found")

        match.ai_match_score = ai_match_score
        match.ai_analysis = ai_analysis
        match.ai_analyzed_at = ai_analyzed_at
        match.updated_at = datetime.now(timezone.utc)
        return match

    @staticmethod
    async def get_user_matches(
        db: AsyncSession,
        user_id: int,
        *,
        min_score: float = 40,
        limit: int = 20,
        offset: int = 0,
    ) -> list[UserJobMatch]:
        stmt = (
            select(UserJobMatch)
            .where(
                and_(
                    UserJobMatch.user_id == user_id,
                    UserJobMatch.skill_match_score >= min_score,
                )
            )
            .order_by(desc(UserJobMatch.skill_match_score))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_user_and_job(
        db: AsyncSession,
        user_id: int,
        job_id: int,
    ) -> Optional[UserJobMatch]:
        stmt = select(UserJobMatch).where(
            and_(UserJobMatch.user_id == user_id, UserJobMatch.job_id == job_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
