"""Repository layer for Job and JobAnalysis database operations."""
import datetime
from typing import Optional

from sqlalchemy import and_, select, String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.jobs.models import SeekJob, JobAnalysis, UserSavedJob, UserJobView
from app.modules.workflow.models import TaskExecution
from app.shared.enums import TaskType
from app.shared.utils import sanitize_nested_text_for_storage


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
            select(SeekJob)
            .options(selectinload(SeekJob.analysis))
            .where(SeekJob.id == job_id)
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
            .where(SeekJob.effective_is_expired.is_(False))  # Only active jobs
            .where(
                SeekJob.listed_at.greater_than(
                    datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
                )
            )
            .order_by(SeekJob.created_at.desc())
            .limit(limit)
        )
        return list[SeekJob](result.scalars().all())

    @staticmethod
    async def get_jobs_without_analysis_task(
        db: AsyncSession,
        limit: int = 100
    ) -> list[SeekJob]:
        """
        Get jobs that have no Job Analysis task record.

        Args:
            db: Database session
            limit: Maximum number of jobs to return

        Returns:
            List of SeekJob instances without Job Analysis workflow
        """
        result = await db.execute(
            select(SeekJob)
            .outerjoin(
                TaskExecution,
                and_(
                    TaskExecution.entity_type == "job",
                    TaskExecution.entity_id == SeekJob.id.cast(String),
                    TaskExecution.task_type == TaskType.JOB_ANALYSIS.value.value,
                ),
            )
            .where(TaskExecution.id.is_(None))  # No task exists
            .where(SeekJob.effective_is_expired.is_(False))  # Only active jobs
            .where(
                SeekJob.listed_at
                > (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30))
            )
            .order_by(SeekJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class JobAnalysisRepository:
    """Repository for JobAnalysis queries."""

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        job_analysis_id: int,
    ) -> Optional[JobAnalysis]:
        """Get JobAnalysis by its primary key."""
        result = await db.execute(
            select(JobAnalysis).where(JobAnalysis.id == job_analysis_id)
        )
        return result.scalar_one_or_none()

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
    async def get_by_ids(
        db: AsyncSession,
        job_analysis_ids: list[int]
    ) -> list[JobAnalysis]:
        if not job_analysis_ids:
            return []
        result = await db.execute(
            select(JobAnalysis).where(JobAnalysis.id.in_(job_analysis_ids))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_ids_with_job(
        db: AsyncSession,
        job_analysis_ids: list[int]
    ) -> list[JobAnalysis]:
        if not job_analysis_ids:
            return []
        result = await db.execute(
            select(JobAnalysis).where(JobAnalysis.id.in_(job_analysis_ids))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_pending_reanalysis(
        db: AsyncSession,
        limit: int = 100
    ) -> list[JobAnalysis]:
        """
        Get job analyses marked for re-analysis.

        Args:
            db: Database session
            limit: Maximum number of records to return

        Returns:
            List of JobAnalysis instances marked for re-analysis
        """
        result = await db.execute(
            select(JobAnalysis)
            .where(JobAnalysis.needs_reanalysis.is_(True))
            .order_by(JobAnalysis.updated_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_updated_since(
        db: AsyncSession,
        *,
        since: datetime.datetime,
        limit: int = 500
    ) -> list[JobAnalysis]:
        """Get job analyses updated since a timestamp."""
        result = await db.execute(
            select(JobAnalysis)
            .where(JobAnalysis.updated_at >= since)
            .order_by(JobAnalysis.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
        analysis_data = sanitize_nested_text_for_storage(analysis_data)
        analysis = JobAnalysis(
            job_id=job_id,
            normalized_job_title=analysis_data.get("normalized_job_title"),
            required_skills=analysis_data.get("required_skills", []),
            preferred_skills=analysis_data.get("preferred_skills", []),
            certifications=analysis_data.get("certifications", []),
            tech_stack=analysis_data.get("tech_stack", []),
            seniority=analysis_data.get("seniority"),
            key_responsibilities=analysis_data.get("key_responsibilities", []),
            experience_years=analysis_data.get("experience_years"),
            education_requirement=analysis_data.get("education_requirement"),
            soft_skills=analysis_data.get("soft_skills", []),
            company_culture_keywords=analysis_data.get(
                "company_culture_keywords", []),
            hiring_priorities=analysis_data.get("hiring_priorities", []),
            analysis_version=analysis_version,
        )
        db.add(analysis)
        await db.flush()
        await db.refresh(analysis)
        return analysis

    @staticmethod
    async def upsert(
        db: AsyncSession,
        job_id: int,
        analysis_data: dict,
        analysis_version: str = "v1.0.0"
    ) -> JobAnalysis:
        """
        Create or update analysis record.

        If analysis exists, update it and clear needs_reanalysis flag.
        Otherwise, create new record.

        Args:
            db: Database session
            job_id: Job ID
            analysis_data: Dictionary containing all analysis fields
            analysis_version: Schema version

        Returns:
            JobAnalysis instance (created or updated)
        """
        analysis_data = sanitize_nested_text_for_storage(analysis_data)
        # Check if analysis exists
        existing = await JobAnalysisRepository.get_by_job_id(db, job_id)

        if existing:
            existing.normalized_job_title = analysis_data.get(
                "normalized_job_title")
            # Update existing record
            existing.required_skills = analysis_data.get("required_skills", [])
            existing.preferred_skills = analysis_data.get(
                "preferred_skills", [])
            existing.certifications = analysis_data.get("certifications", [])
            existing.tech_stack = analysis_data.get("tech_stack", [])
            existing.seniority = analysis_data.get("seniority")
            existing.key_responsibilities = analysis_data.get(
                "key_responsibilities", [])
            existing.experience_years = analysis_data.get("experience_years")
            existing.education_requirement = analysis_data.get(
                "education_requirement")
            existing.soft_skills = analysis_data.get("soft_skills", [])
            existing.company_culture_keywords = analysis_data.get(
                "company_culture_keywords", [])
            existing.hiring_priorities = analysis_data.get(
                "hiring_priorities", [])
            existing.cn_content = analysis_data.get("cn_content")
            existing.analysis_version = analysis_version
            existing.needs_reanalysis = False  # Clear re-analysis flag

            await db.flush()
            await db.refresh(existing)
            return existing
        else:
            # Create new record
            analysis = JobAnalysis(
                job_id=job_id,
                normalized_job_title=analysis_data.get("normalized_job_title"),
                required_skills=analysis_data.get("required_skills", []),
                preferred_skills=analysis_data.get("preferred_skills", []),
                certifications=analysis_data.get("certifications", []),
                tech_stack=analysis_data.get("tech_stack", []),
                seniority=analysis_data.get("seniority"),
                key_responsibilities=analysis_data.get(
                    "key_responsibilities", []),
                experience_years=analysis_data.get("experience_years"),
                education_requirement=analysis_data.get(
                    "education_requirement"),
                soft_skills=analysis_data.get("soft_skills", []),
                company_culture_keywords=analysis_data.get(
                    "company_culture_keywords", []),
                hiring_priorities=analysis_data.get("hiring_priorities", []),
                cn_content=analysis_data.get("cn_content"),
                analysis_version=analysis_version,
                needs_reanalysis=False,
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


class SavedJobRepository:
    """Repository for user saved jobs."""

    @staticmethod
    async def get_by_user_and_job(
        db: AsyncSession,
        user_id: int,
        job_id: int,
    ) -> Optional[UserSavedJob]:
        result = await db.execute(
            select(UserSavedJob).where(
                and_(UserSavedJob.user_id == user_id, UserSavedJob.job_id == job_id)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        job_id: int,
    ) -> UserSavedJob:
        saved = UserSavedJob(user_id=user_id, job_id=job_id)
        db.add(saved)
        await db.flush()
        await db.refresh(saved)
        return saved

    @staticmethod
    async def delete_by_user_and_job(
        db: AsyncSession,
        user_id: int,
        job_id: int,
    ) -> bool:
        saved = await SavedJobRepository.get_by_user_and_job(db, user_id, job_id)
        if not saved:
            return False
        await db.delete(saved)
        await db.flush()
        return True

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[UserSavedJob, SeekJob]], int]:
        count_result = await db.execute(
            select(func.count()).select_from(UserSavedJob).where(UserSavedJob.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(UserSavedJob, SeekJob)
            .join(SeekJob, SeekJob.id == UserSavedJob.job_id)
            .where(UserSavedJob.user_id == user_id)
            .order_by(UserSavedJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all()), total


class UserJobViewRepository:
    """Repository for user viewed jobs."""

    @staticmethod
    async def get_by_user_and_job(
        db: AsyncSession,
        user_id: int,
        job_id: int,
    ) -> Optional[UserJobView]:
        result = await db.execute(
            select(UserJobView).where(
                and_(UserJobView.user_id == user_id, UserJobView.job_id == job_id)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_viewed(
        db: AsyncSession,
        user_id: int,
        job_id: int,
    ) -> UserJobView:
        now = datetime.datetime.now(datetime.timezone.utc)
        existing = await UserJobViewRepository.get_by_user_and_job(db, user_id, job_id)
        if existing:
            existing.last_viewed_at = now
            existing.view_count = max(1, existing.view_count) + 1
            await db.flush()
            await db.refresh(existing)
            return existing

        viewed = UserJobView(
            user_id=user_id,
            job_id=job_id,
            first_viewed_at=now,
            last_viewed_at=now,
            view_count=1,
        )
        db.add(viewed)
        try:
            await db.flush()
            await db.refresh(viewed)
            return viewed
        except IntegrityError:
            await db.rollback()
            # Handle rare race condition on unique(user_id, job_id).
            existing = await UserJobViewRepository.get_by_user_and_job(db, user_id, job_id)
            if not existing:
                raise
            existing.last_viewed_at = now
            existing.view_count = max(1, existing.view_count) + 1
            await db.flush()
            await db.refresh(existing)
            return existing

    @staticmethod
    async def get_view_map(
        db: AsyncSession,
        user_id: int,
        job_ids: list[int],
    ) -> dict[int, UserJobView]:
        if not job_ids:
            return {}

        result = await db.execute(
            select(UserJobView).where(
                and_(
                    UserJobView.user_id == user_id,
                    UserJobView.job_id.in_(job_ids),
                )
            )
        )
        views = result.scalars().all()
        return {view.job_id: view for view in views}
