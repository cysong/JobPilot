"""
Job service layer - business logic for job operations.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select, func, or_, and_, distinct, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.modules.jobs.models import SeekJob, UserJobView
from app.modules.jobs.repository import (
    BRIEF_COLUMNS,
    JobRepository,
    SavedJobRepository,
    UserJobViewRepository,
)
from app.modules.applications.models import Application
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.schemas import (
    JobFiltersRequest,
    JobFiltersOptions,
    JobBase,
    JobEnqueueResponse,
    SavedJobItem,
    SavedJobListResponse,
    SavedJobStatus,
    JobViewedStatus,
    JobExpirationStatus,
)
from app.modules.auth.models import User
from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from app.shared.pagination import PaginationParams


logger = logging.getLogger(__name__)


class JobService:
    """Service class for Job-related operations"""

    @staticmethod
    async def get_jobs(
        db: AsyncSession,
        filters: JobFiltersRequest,
        pagination: PaginationParams,
        user_id: int,
    ) -> tuple[list[JobBase], int]:
        """
        Get paginated job list with filtering.

        Args:
            db: Database session
            filters: Filter parameters
            pagination: Pagination parameters

        Returns:
            Tuple of (job_list, total_count)
        """
        has_application_expr = exists(
            select(1).where(
                and_(
                    Application.user_id == user_id,
                    Application.is_deleted.is_(False),
                    Application.job_id == SeekJob.id,
                )
            )
        ).label("has_application")

        # Base query — list responses materialize JobBase, which never reads
        # ``content``. Apply load_only so the heavy column doesn't ride along.
        query = (
            select(SeekJob, has_application_expr)
            .options(load_only(*BRIEF_COLUMNS))
        )

        # Apply keyword search (title + abstract + content + company names).
        # The ilike on content stays in the WHERE clause for behavior parity
        # — load_only above only narrows the SELECT column list, it doesn't
        # affect what columns the filter can reference.
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

        # Apply company filter (case-insensitive: dropdown shows a casefold-
        # deduped option per company, so the list query must match all case
        # variants too — otherwise selecting "fuel50" misses rows stored as
        # "Fuel50" from another scraper).
        if filters.companies:
            normalized_companies = [c.lower() for c in filters.companies]
            query = query.where(
                or_(
                    func.lower(SeekJob.advertiser_name).in_(normalized_companies),
                    func.lower(SeekJob.company_name).in_(normalized_companies),
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

        # Exclude expired jobs
        if filters.hide_expired:
            query = query.where(SeekJob.effective_is_expired.is_(False))

        # Apply viewed status filter
        if filters.view_status == "viewed":
            query = query.where(
                exists(
                    select(1).where(
                        and_(
                            UserJobView.user_id == user_id,
                            UserJobView.job_id == SeekJob.id,
                        )
                    )
                )
            )
        elif filters.view_status == "unviewed":
            query = query.where(
                ~exists(
                    select(1).where(
                        and_(
                            UserJobView.user_id == user_id,
                            UserJobView.job_id == SeekJob.id,
                        )
                    )
                )
            )

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
        rows = result.all()

        job_list = [row[0] for row in rows]
        has_application_map = {row[0].id: bool(row[1]) for row in rows}
        job_ids = [job.id for job in job_list]
        view_map = await UserJobViewRepository.get_view_map(db, user_id, job_ids)

        job_items: list[JobBase] = []
        for job in job_list:
            item = JobBase.model_validate(job)
            view = view_map.get(job.id)
            item.is_viewed = view is not None
            item.last_viewed_at = view.last_viewed_at if view else None
            item.has_application = has_application_map.get(job.id, False)
            job_items.append(item)

        return job_items, total

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
        # Get distinct location cities (NZ only)
        cities_query = (
            select(distinct(SeekJob.location_city))
            .where(
                and_(
                    SeekJob.location_city.isnot(None),
                    SeekJob.location_city != "",
                    SeekJob.country_code == "NZ",
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
    async def search_companies(
        db: AsyncSession,
        keyword: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        """
        Search companies for filter dropdown using both company_name and advertiser_name.

        Args:
            db: Database session
            keyword: Optional keyword for fuzzy search
            limit: Maximum companies to return

        Returns:
            Deduplicated company list
        """
        normalized_limit = max(1, min(limit, 50))
        # Over-fetch slightly so we can preserve requested size after case-insensitive dedupe.
        fetch_limit = normalized_limit * 3

        normalized_company_name = func.trim(SeekJob.company_name)
        normalized_advertiser_name = func.trim(SeekJob.advertiser_name)

        company_name_query = (
            select(normalized_company_name.label("company"))
            .where(
                and_(
                    SeekJob.company_name.isnot(None),
                    normalized_company_name != "",
                )
            )
        )
        advertiser_name_query = (
            select(normalized_advertiser_name.label("company"))
            .where(
                and_(
                    SeekJob.advertiser_name.isnot(None),
                    normalized_advertiser_name != "",
                )
            )
        )

        if keyword:
            pattern = f"%{keyword.strip()}%"
            company_name_query = company_name_query.where(
                normalized_company_name.ilike(pattern)
            )
            advertiser_name_query = advertiser_name_query.where(
                normalized_advertiser_name.ilike(pattern)
            )

        merged_query = (
            company_name_query.union(advertiser_name_query).subquery()
        )
        query = (
            select(merged_query.c.company)
            .order_by(merged_query.c.company)
            .limit(fetch_limit)
        )

        result = await db.execute(query)
        raw_companies = [name for name in result.scalars().all() if name]

        deduped_companies: list[str] = []
        seen_keys: set[str] = set()
        for company in raw_companies:
            normalized_key = company.casefold()
            if normalized_key in seen_keys:
                continue
            seen_keys.add(normalized_key)
            deduped_companies.append(company)
            if len(deduped_companies) >= normalized_limit:
                break

        return deduped_companies

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
        # Only need company_name / advertiser_name / classification on the
        # current job; use the brief loader to avoid pulling content/analysis.
        current_job = await JobRepository.get_brief(db, job_id)
        if not current_job:
            return []

        # Similar-jobs result feeds JobBase on the frontend, so brief columns
        # are sufficient — apply load_only here too.
        query = (
            select(SeekJob)
            .options(load_only(*BRIEF_COLUMNS))
            .where(
                and_(
                    SeekJob.id != job_id,  # Exclude current job
                    SeekJob.effective_is_expired.is_(False),
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

    @staticmethod
    async def get_saved_status(
        db: AsyncSession,
        user: User,
        job_id: int,
    ) -> SavedJobStatus:
        if not await JobRepository.exists(db, job_id):
            raise NotFoundError("Job not found")

        saved = await SavedJobRepository.get_by_user_and_job(db, user.id, job_id)
        if not saved:
            return SavedJobStatus(is_saved=False, saved_at=None)

        return SavedJobStatus(is_saved=True, saved_at=saved.created_at)

    @staticmethod
    async def get_viewed_status(
        db: AsyncSession,
        user: User,
        job_id: int,
    ) -> JobViewedStatus:
        if not await JobRepository.exists(db, job_id):
            raise NotFoundError("Job not found")

        viewed = await UserJobViewRepository.get_by_user_and_job(db, user.id, job_id)
        if not viewed:
            return JobViewedStatus(
                is_viewed=False,
                first_viewed_at=None,
                last_viewed_at=None,
                view_count=0,
            )

        return JobViewedStatus(
            is_viewed=True,
            first_viewed_at=viewed.first_viewed_at,
            last_viewed_at=viewed.last_viewed_at,
            view_count=viewed.view_count,
        )

    @staticmethod
    async def mark_job_viewed(
        db: AsyncSession,
        user: User,
        job_id: int,
    ) -> JobViewedStatus:
        if not await JobRepository.exists(db, job_id):
            raise NotFoundError("Job not found")

        viewed = await UserJobViewRepository.mark_viewed(db, user.id, job_id)
        await db.commit()
        return JobViewedStatus(
            is_viewed=True,
            first_viewed_at=viewed.first_viewed_at,
            last_viewed_at=viewed.last_viewed_at,
            view_count=viewed.view_count,
        )

    @staticmethod
    async def save_job(
        db: AsyncSession,
        user: User,
        job_id: int,
    ) -> SavedJobStatus:
        if not await JobRepository.exists(db, job_id):
            raise NotFoundError("Job not found")

        saved = await SavedJobRepository.get_by_user_and_job(db, user.id, job_id)
        if not saved:
            saved = await SavedJobRepository.create(db, user.id, job_id)
            await db.commit()

        return SavedJobStatus(is_saved=True, saved_at=saved.created_at)

    @staticmethod
    async def unsave_job(
        db: AsyncSession,
        user: User,
        job_id: int,
    ) -> SavedJobStatus:
        if not await JobRepository.exists(db, job_id):
            raise NotFoundError("Job not found")

        deleted = await SavedJobRepository.delete_by_user_and_job(db, user.id, job_id)
        if deleted:
            await db.commit()

        return SavedJobStatus(is_saved=False, saved_at=None)

    @staticmethod
    async def list_saved_jobs(
        db: AsyncSession,
        user: User,
        pagination: PaginationParams,
    ) -> SavedJobListResponse:
        rows, total = await SavedJobRepository.list_by_user(
            db,
            user.id,
            offset=pagination.get_offset(),
            limit=pagination.get_limit(),
        )
        items: list[SavedJobItem] = []
        job_ids = [job.id for _, job in rows]
        view_map = await UserJobViewRepository.get_view_map(db, user.id, job_ids)
        application_job_ids = await ApplicationRepository.get_job_id_set_by_user(
            db,
            user.id,
            job_ids,
        )
        for saved, job in rows:
            job_item = JobBase.model_validate(job)
            # Keep saved cards visually aligned with list cards when source logo is missing.
            if not job_item.company_logo and job.branding_logo_url:
                job_item.company_logo = job.branding_logo_url
            viewed = view_map.get(job.id)
            job_item.is_viewed = viewed is not None
            job_item.last_viewed_at = viewed.last_viewed_at if viewed else None
            job_item.has_application = job.id in application_job_ids
            items.append(
                SavedJobItem(
                    job=job_item,
                    saved_at=saved.created_at,
                )
            )
        return SavedJobListResponse.create(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    @staticmethod
    async def set_manual_expiration(
        db: AsyncSession,
        user: User,
        job_id: int,
        *,
        manual_expired: bool,
        note: str | None = None,
    ) -> JobExpirationStatus:
        """Set manual expiration status for a job."""
        job = await JobRepository.get_by_id(db, job_id)
        if not job:
            raise NotFoundError("Job not found")

        if manual_expired:
            job.manual_expired = True
            job.manual_expired_by = user.id
            job.manual_expired_at = datetime.now(timezone.utc)
            job.manual_expired_note = note
        else:
            job.manual_expired = False
            job.manual_expired_by = None
            job.manual_expired_at = None
            job.manual_expired_note = None

        await db.commit()
        await db.refresh(job)

        return JobExpirationStatus(
            job_id=job.id,
            is_expired=job.effective_is_expired,
            manual_expired=bool(job.manual_expired),
            manual_expired_by=job.manual_expired_by,
            manual_expired_at=job.manual_expired_at,
            manual_expired_note=job.manual_expired_note,
        )

    @staticmethod
    async def enqueue_job_url(db: AsyncSession, url: str) -> JobEnqueueResponse:
        """Forward `url` to the AWS Function URL and shape the response.

        Mapping (see docs/manual_job_enqueue_design.md):
        - 200 enqueued=true               -> return as-is
        - 200 enqueued=false already_in_db -> resolve existing_job_id
        - 400 (any AWS error)             -> BadRequestError(error_text)
        - 401 / 500 / network / timeout   -> ServiceUnavailableError
        - missing config                  -> ServiceUnavailableError
        """
        api_url = settings.ENQUEUE_API_URL
        api_key = settings.ENQUEUE_API_KEY
        if not api_url or not api_key:
            logger.warning("ENQUEUE_API_URL/KEY not configured")
            raise ServiceUnavailableError("Manual enqueue is not configured")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    api_url,
                    headers={
                        "X-API-Key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={"url": url},
                )
        except httpx.HTTPError as exc:
            logger.warning("Enqueue API network error: %s", exc)
            raise ServiceUnavailableError("Enqueue service unavailable") from exc

        # Try to parse JSON; tolerate empty/non-JSON 5xx responses.
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}

        if resp.status_code == 200:
            enqueued = bool(body.get("enqueued"))
            source = body.get("source")
            source_id = body.get("source_id")
            reason = body.get("reason")
            existing_job_id: int | None = None

            if not enqueued and reason == "already_in_db" and source and source_id:
                existing = await JobRepository.get_by_source_and_source_id(
                    db, source, source_id
                )
                if existing is not None:
                    existing_job_id = existing.id

            return JobEnqueueResponse(
                enqueued=enqueued,
                source=source,
                source_id=source_id,
                reason=reason,
                existing_job_id=existing_job_id,
            )

        if resp.status_code == 400:
            error_text = str(body.get("error") or "Bad request")
            raise BadRequestError(error_text)

        # 401, 500, anything else: hide upstream specifics.
        request_id = body.get("request_id")
        logger.warning(
            "Enqueue API non-200: status=%s body=%s request_id=%s",
            resp.status_code,
            body,
            request_id,
        )
        raise ServiceUnavailableError("Enqueue service unavailable")
