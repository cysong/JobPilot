"""Repository layer for Job and JobAnalysis database operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from typing import Optional

from app.modules.jobs.models import SeekJob, JobAnalysis


class JobRepository:
    """Repository for SeekJob queries."""

    @staticmethod
    async def get_by_id(db: AsyncSession, job_id: int) -> Optional[SeekJob]:
        """
        Get job by ID.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            SeekJob instance or None if not found
        """
        result = await db.execute(
            select(SeekJob).where(SeekJob.id == job_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_unanalyzed_jobs(
        db: AsyncSession,
        limit: int = 100
    ) -> list[SeekJob]:
        """
        Get jobs that have no analysis record yet.

        Used by polling task to find jobs needing analysis.
        Only returns active (non-expired) jobs.

        Args:
            db: Database session
            limit: Maximum number of jobs to return

        Returns:
            List of SeekJob instances without analysis
        """
        result = await db.execute(
            select(SeekJob)
            .outerjoin(JobAnalysis, SeekJob.id == JobAnalysis.job_id)
            .where(JobAnalysis.id.is_(None))  # No analysis exists
            .where(SeekJob.is_expired == False)  # Only active jobs
            .limit(limit)
        )
        return list(result.scalars().all())


class JobAnalysisRepository:
    """Repository for JobAnalysis queries."""

    @staticmethod
    async def get_by_job_id(
        db: AsyncSession,
        job_id: int
    ) -> Optional[JobAnalysis]:
        """
        Get cached analysis by job_id.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            JobAnalysis instance or None if not found
        """
        result = await db.execute(
            select(JobAnalysis).where(JobAnalysis.job_id == job_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        job_id: int,
        analysis_data: dict,
        analysis_version: str = "v1.0.0"
    ) -> JobAnalysis:
        """
        Create new analysis record.

        Only called on successful AI analysis.

        Args:
            db: Database session
            job_id: Job ID
            analysis_data: Dictionary containing all analysis fields
            analysis_version: Schema version

        Returns:
            Created JobAnalysis instance
        """
        analysis = JobAnalysis(
            job_id=job_id,
            required_skills=analysis_data.get("required_skills", []),
            preferred_skills=analysis_data.get("preferred_skills", []),
            certifications=analysis_data.get("certifications", []),
            tech_stack=analysis_data.get("tech_stack", []),
            seniority=analysis_data.get("seniority"),
            key_responsibilities=analysis_data.get("key_responsibilities", []),
            experience_years=analysis_data.get("experience_years"),
            education_requirement=analysis_data.get("education_requirement"),
            soft_skills=analysis_data.get("soft_skills", []),
            company_culture_keywords=analysis_data.get("company_culture_keywords", []),
            hiring_priorities=analysis_data.get("hiring_priorities", []),
            analysis_version=analysis_version,
        )
        db.add(analysis)
        await db.flush()
        await db.refresh(analysis)
        return analysis

    @staticmethod
    async def delete_by_job_id(db: AsyncSession, job_id: int) -> bool:
        """
        Delete analysis for a job (for re-analysis).

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            True if deleted, False if not found
        """
        analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
        if analysis:
            await db.delete(analysis)
            await db.flush()
            return True
        return False
