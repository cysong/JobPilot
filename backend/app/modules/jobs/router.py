"""
Job API endpoints.
"""
from typing import Annotated, Literal, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.jobs import service
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository
from app.modules.jobs.schemas import (
    JobAnalysisResponse,
    JobBase,
    JobDetail,
    JobEnqueueRequest,
    JobEnqueueResponse,
    JobExpirationStatus,
    JobExpirationUpdateRequest,
    JobFiltersOptions,
    JobFiltersRequest,
    JobListResponse,
    SavedJobListResponse,
    SavedJobStatus,
    SourceMeta,
    JobViewedStatus,
)
from app.modules.jobs.source_config import load_source_metas
from app.modules.matching import service as matching_service
from app.modules.matching.schemas import MatchDetail, MatchListResponse
from app.shared.pagination import PaginationParams
from app.modules.workflow import TaskService
from app.shared.enums import EntityType, TaskType
from app.modules.applications.service import ApplicationService
from app.modules.applications.schemas import ApplicationDetail

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/matches", response_model=MatchListResponse)
async def list_my_matches(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    view: Literal["recommended", "rejected"] = Query("recommended"),
    tiers: Optional[str] = Query(None, description="Comma-separated tiers for the recommended view, default A,B"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Matching v3 results for the current user on live jobs, newest first."""
    tier_list = [t.strip().upper() for t in tiers.split(",") if t.strip()] if tiers else None
    return await matching_service.list_matches(db, current_user, view=view, tiers=tier_list,
                                               limit=limit, offset=offset)


@router.get("/matches/{job_id}", response_model=MatchDetail | None)
async def get_my_match_detail(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Full matching v3 judgment for the current user on a job (null if none)."""
    return await matching_service.get_match_detail(db, current_user, job_id)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    keyword: str | None = Query(None, description="Search keyword"),
    location_cities: list[str] | None = Query(None, description="Filter by cities"),
    work_types: list[str] | None = Query(None, description="Filter by work types"),
    companies: list[str] | None = Query(None, description="Filter by companies"),
    sources: list[str] | None = Query(None, description="Filter by sources"),
    view_status: str = Query("all", pattern="^(all|viewed|unviewed)$", description="Viewed status filter"),
    hide_expired: bool = Query(False, description="Exclude expired jobs"),
    listed_after: str | None = Query(None, description="Listed after date (ISO format)"),
    listed_before: str | None = Query(None, description="Listed before date (ISO format)"),
    params: PaginationParams = Depends(),
    sort_by: str = Query("listed_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """Get paginated job list with filtering and search."""
    parsed_listed_after = None
    parsed_listed_before = None

    if listed_after:
        try:
            parsed_listed_after = datetime.fromisoformat(listed_after)
        except ValueError:
            raise BadRequestError("Invalid listed_after date format")

    if listed_before:
        try:
            parsed_listed_before = datetime.fromisoformat(listed_before)
        except ValueError:
            raise BadRequestError("Invalid listed_before date format")

    filters = JobFiltersRequest(
        keyword=keyword,
        location_cities=location_cities,
        work_types=work_types,
        companies=companies,
        sources=sources,
        view_status=view_status,
        hide_expired=hide_expired,
        listed_after=parsed_listed_after,
        listed_before=parsed_listed_before,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    job_items, total = await service.JobService.get_jobs(db, filters, params, current_user.id)

    return JobListResponse.create(
        items=job_items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/saved", response_model=SavedJobListResponse)
async def list_saved_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    params: PaginationParams = Depends(),
):
    """List saved jobs for current user."""
    return await service.JobService.list_saved_jobs(db, current_user, params)


@router.get("/filters", response_model=JobFiltersOptions)
async def get_filter_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get available filter options for UI dropdowns."""
    return await service.JobService.get_filter_options(db)


@router.get("/filters/companies", response_model=list[str])
async def search_company_filters(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(None, description="Company keyword"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of companies"),
):
    """Search company options for company filter dropdown."""
    return await service.JobService.search_companies(db, q, limit)


@router.get("/sources/meta", response_model=list[SourceMeta])
async def get_source_metas(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Return display metadata for all known job sources.

    Icons are bundled in the frontend and keyed by `key`; the backend only
    owns label / brand_color / flags. Loaded from backend/config/sources.yaml
    and memoized per-process (restart the API to pick up changes).
    """
    return load_source_metas()


@router.post("/enqueue", response_model=JobEnqueueResponse)
async def enqueue_job_url(
    payload: JobEnqueueRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manually submit a job URL to the external AWS scraper.

    Any logged-in user may call this. The actual scrape happens
    asynchronously on AWS; this endpoint only reports enqueue status.
    """
    return await service.JobService.enqueue_job_url(db, payload.url)


@router.get("/{job_id}/saved", response_model=SavedJobStatus)
async def get_job_saved_status(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get saved status for current user and job."""
    return await service.JobService.get_saved_status(db, current_user, job_id)


@router.get("/{job_id}/viewed", response_model=JobViewedStatus)
async def get_job_viewed_status(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get viewed status for current user and job."""
    return await service.JobService.get_viewed_status(db, current_user, job_id)


@router.post("/{job_id}/viewed", response_model=JobViewedStatus)
async def mark_job_viewed(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Mark a job as viewed for current user."""
    return await service.JobService.mark_job_viewed(db, current_user, job_id)


@router.post("/{job_id}/saved", response_model=SavedJobStatus)
async def save_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Save a job for current user."""
    return await service.JobService.save_job(db, current_user, job_id)


@router.patch("/{job_id}/expiration", response_model=JobExpirationStatus)
async def set_job_expiration(
    job_id: int,
    payload: JobExpirationUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manually mark/unmark job as expired globally with operator tracking."""
    return await service.JobService.set_manual_expiration(
        db=db,
        user=current_user,
        job_id=job_id,
        manual_expired=payload.manual_expired,
        note=payload.note,
    )


@router.delete("/{job_id}/saved", response_model=SavedJobStatus)
async def unsave_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Remove job from saved list for current user."""
    return await service.JobService.unsave_job(db, current_user, job_id)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job_detail(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get detailed job information by ID."""
    job = await service.JobService.get_job_by_id(db, job_id)

    if not job:
        raise NotFoundError("Job not found")

    # Build response with analysis (includes cn_content) and convenience content_cn for UI toggle
    job_detail = JobDetail.model_validate(job)
    await service.JobService.apply_user_state(db, current_user.id, [job_detail])
    if job.analysis:
        job_detail.analysis = JobAnalysisResponse.model_validate(job.analysis)
        job_detail.content_cn = job.analysis.cn_content
    return job_detail


@router.get("/{job_id}/similar", response_model=list[JobBase])
async def get_similar_jobs(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(5, ge=1, le=10, description="Number of similar jobs to return"),
):
    """Get similar jobs from the same company and classification."""
    similar_jobs = await service.JobService.get_similar_jobs(db, job_id, limit)

    items = [JobBase.model_validate(job) for job in similar_jobs]
    await service.JobService.apply_user_state(db, current_user.id, items)
    return items


@router.get("/{job_id}/analysis", response_model=JobAnalysisResponse)
async def get_job_analysis(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get cached job analysis."""
    analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not analysis:
        raise NotFoundError(f"Analysis not found for job {job_id}. Try triggering analysis first.")

    return JobAnalysisResponse.model_validate(analysis)


@router.post("/{job_id}/analyze")
async def trigger_job_analysis(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manually trigger job analysis (test/debug only)."""
    if not await JobRepository.exists(db, job_id):
        raise NotFoundError("Job not found")

    task = await TaskService.submit_task(
        db=db,
        task_type=TaskType.JOB_ANALYSIS,
        entity_type=EntityType.JOB.value,
        entity_id=job_id,
        user_id=current_user.id,
        input_data={"job_id": job_id},
    )

    return {
        "message": "Analysis triggered",
        "celery_task_id": task.id,
        "job_id": job_id
    }


@router.delete("/{job_id}/analysis")
async def delete_job_analysis(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete cached job analysis (for re-analysis testing)."""
    deleted = await JobAnalysisRepository.delete_by_job_id(db, job_id)
    if not deleted:
        raise NotFoundError("Analysis not found")

    await db.commit()

    return {
        "message": f"Analysis for job {job_id} deleted successfully",
    }


@router.get("/{job_id}/application", response_model=ApplicationDetail | None)
async def get_job_application(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current user's application for this job."""
    application = await ApplicationService.get_application_by_job_id(db, current_user, job_id)
    return application
