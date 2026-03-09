"""
Job service layer - business logic for job operations.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, or_, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.jobs.models import SeekJob
from app.modules.jobs.schemas import JobFiltersRequest, JobFiltersOptions
from app.shared.pagination import PaginationParams


class JobService:
    """Service class for Job-related operations"""

    @staticmethod
    async def get_jobs(
        db: AsyncSession,
        filters: JobFiltersRequest,
        pagination: PaginationParams,
    ) -> tuple[list[SeekJob], int]:
        """
        Get paginated job list with filtering.

        Args:
            db: Database session
            filters: Filter parameters
            pagination: Pagination parameters

        Returns:
            Tuple of (job_list, total_count)
        """
        # Base query
        query = select(SeekJob).where(SeekJob.is_expired == False)

        # Apply keyword search (title + abstract + content + company names)
        if filters.keyword:
            search_pattern = f"%{filters.keyword}%"
            query = query.where(
                or_(
                    SeekJob.title.ilike(search_pattern),
                    SeekJob.abstract.ilike(search_pattern),
                    SeekJob.content.ilike(search_pattern),
                    SeekJob.advertiser_name.ilike(search_pattern),
                    SeekJob.company_name.ilike(search_pattern)
                )
            )

        # Apply location filter
        if filters.location_cities:
            query = query.where(SeekJob.location_city.in_(filters.location_cities))

        # Apply work type filter
        if filters.work_types:
            # Work types are stored as comma-separated or label format
            # Use LIKE to match any of the selected types
            work_type_conditions = [
                SeekJob.work_types_label.ilike(f"%{wt}%") for wt in filters.work_types
            ]
            query = query.where(or_(*work_type_conditions))

        # Apply company filter
        if filters.companies:
            query = query.where(
                or_(
                    SeekJob.advertiser_name.in_(filters.companies),
                    SeekJob.company_name.in_(filters.companies)
                )
            )

        # Apply source filter
        if filters.sources:
            query = query.where(SeekJob.source.in_(filters.sources))

        # Apply date range filter
        if filters.listed_after:
            query = query.where(SeekJob.listed_at >= filters.listed_after)

        if filters.listed_before:
            query = query.where(SeekJob.listed_at <= filters.listed_before)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply sorting
        if filters.sort_by == "listed_at":
            sort_column = SeekJob.listed_at
        elif filters.sort_by == "title":
            sort_column = SeekJob.title
        else:
            sort_column = SeekJob.listed_at

        if filters.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

        # Execute query
        result = await db.execute(query)
        jobs = result.scalars().all()

        return list(jobs), total

    @staticmethod
    async def get_job_by_id(db: AsyncSession, job_id: int) -> Optional[SeekJob]:
        """
        Get job by ID.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            SeekJob instance or None
        """
        query = (
            select(SeekJob)
            .options(selectinload(SeekJob.analysis))
            .where(SeekJob.id == job_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_filter_options(db: AsyncSession) -> JobFiltersOptions:
        """
        Get available filter options for UI dropdowns.

        Args:
            db: Database session

        Returns:
            JobFiltersOptions with available values
        """
        # Get distinct location cities
        cities_query = (
            select(distinct(SeekJob.location_city))
            .where(
                and_(
                    SeekJob.location_city.isnot(None),
                    SeekJob.location_city != "",
                    SeekJob.is_expired == False
                )
            )
            .order_by(SeekJob.location_city)
            .limit(100)  # Limit to avoid too many options
        )
        cities_result = await db.execute(cities_query)
        cities = [city for city in cities_result.scalars().all() if city]

        # Get distinct work types (parse from work_types_label)
        work_types_query = (
            select(distinct(SeekJob.work_types_label))
            .where(
                and_(
                    SeekJob.work_types_label.isnot(None),
                    SeekJob.work_types_label != "",
                    SeekJob.is_expired == False
                )
            )
            .limit(50)
        )
        work_types_result = await db.execute(work_types_query)
        work_types = [wt for wt in work_types_result.scalars().all() if wt]

        # Get distinct companies (prefer company_name, fallback to advertiser_name)
        companies_query = (
            select(distinct(SeekJob.company_name))
            .where(
                and_(
                    SeekJob.company_name.isnot(None),
                    SeekJob.company_name != "",
                    SeekJob.is_expired == False
                )
            )
            .order_by(SeekJob.company_name)
            .limit(100)
        )
        companies_result = await db.execute(companies_query)
        companies = [company for company in companies_result.scalars().all() if company]

        # If company_name is empty, try advertiser_name
        if not companies:
            advertiser_query = (
                select(distinct(SeekJob.advertiser_name))
                .where(
                    and_(
                        SeekJob.advertiser_name.isnot(None),
                        SeekJob.advertiser_name != "",
                        SeekJob.is_expired == False
                    )
                )
                .order_by(SeekJob.advertiser_name)
                .limit(100)
            )
            advertiser_result = await db.execute(advertiser_query)
            companies = [adv for adv in advertiser_result.scalars().all() if adv]

        # Get distinct sources
        sources_query = (
            select(distinct(SeekJob.source))
            .where(
                and_(
                    SeekJob.source.isnot(None),
                    SeekJob.source != "",
                    SeekJob.is_expired == False,
                )
            )
            .order_by(SeekJob.source)
            .limit(50)
        )
        sources_result = await db.execute(sources_query)
        sources = [source for source in sources_result.scalars().all() if source]

        return JobFiltersOptions(
            location_cities=cities,
            work_types=work_types,
            companies=companies,
            sources=sources,
        )

    @staticmethod
    async def get_similar_jobs(
        db: AsyncSession,
        job_id: int,
        limit: int = 5
    ) -> list[SeekJob]:
        """
        Get similar jobs from the same company and classification.

        Args:
            db: Database session
            job_id: Current job ID
            limit: Maximum number of similar jobs to return

        Returns:
            List of similar SeekJob instances
        """
        # First, get the current job to know company and classification
        current_job = await JobService.get_job_by_id(db, job_id)
        if not current_job:
            return []

        # Build query for similar jobs
        query = (
            select(SeekJob)
            .where(
                and_(
                    SeekJob.id != job_id,  # Exclude current job
                    SeekJob.is_expired == False,
                    or_(
                        SeekJob.company_name == current_job.company_name,
                        SeekJob.advertiser_name == current_job.advertiser_name
                    ),
                    SeekJob.classification == current_job.classification
                )
            )
            .order_by(SeekJob.listed_at.desc())
            .limit(limit)
        )

        result = await db.execute(query)
        return list(result.scalars().all())
