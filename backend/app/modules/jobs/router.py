"""
Job API endpoints.
"""
from typing import Annotated
from datetime import datetime

from celery.app.task import TaskType
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.jobs import service
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository, UserJobViewRepository
from app.modules.jobs.schemas import (
    JobAnalysisResponse,
    JobBase,
    JobBriefInfo,
    JobDetail,
    JobFiltersOptions,
    JobFiltersRequest,
    JobListResponse,
    ResumeBriefInfo,
    SavedJobListResponse,
    SavedJobStatus,
    JobViewedStatus,
    UserJobMatchDetailResponse,
    UserJobMatchResponse,
)
from app.modules.matching.repository import UserJobMatchRepository
from app.modules.resumes.repository import ResumeRepository
from app.shared.pagination import PaginationParams
from app.modules.workflow import TaskService
from app.shared.enums import EntityType
from app.modules.applications.service import ApplicationService
from app.modules.applications.schemas import ApplicationDetail

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/matches", response_model=list[UserJobMatchResponse])
async def list_my_matches(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    min_score: float = Query(40, ge=0, le=100, description="Minimum skill match score"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List matches for current user."""
    matches = await UserJobMatchRepository.get_user_matches(
        db=db,
        user_id=current_user.id,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )

    view_map = await UserJobViewRepository.get_view_map(
        db=db,
        user_id=current_user.id,
        job_ids=[match.job_id for match in matches],
    )

    results: list[UserJobMatchResponse] = []
    for match in matches:
        job = await JobRepository.get_by_id(db, match.job_id)
        if not job:
            continue
        resume = None
        if match.recommended_resume_id:
            resume = await ResumeRepository.get_by_id(db, match.recommended_resume_id)

        job_info = JobBriefInfo.model_validate(job)
        viewed = view_map.get(match.job_id)
        job_info.is_viewed = viewed is not None
        job_info.last_viewed_at = viewed.last_viewed_at if viewed else None

        results.append(
            UserJobMatchResponse(
                id=match.id,
                job=job_info,
                skill_match_score=match.skill_match_score,
                resume_match_score=match.resume_match_score,
                ai_match_score=match.ai_match_score,
                recommended_resume=ResumeBriefInfo.model_validate(resume)
                if resume
                else None,
                skill_match_details=match.skill_match_details,
                ai_analysis=match.ai_analysis,
                calculated_at=match.calculated_at,
                ai_analyzed_at=match.ai_analyzed_at,
            )
        )

    return results


@router.get("/matches/{job_id}", response_model=UserJobMatchDetailResponse | None)
async def get_my_match_detail(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get match detail for current user on a specific job."""
    match = await UserJobMatchRepository.get_by_user_and_job(
        db=db,
        user_id=current_user.id,
        job_id=job_id,
    )
    if not match:
        return None

    job = await JobRepository.get_by_id(db, job_id)
    job_analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not job or not job_analysis:
        raise NotFoundError("Job or analysis not found")
    resume = None
    if match.recommended_resume_id:
        resume = await ResumeRepository.get_by_id(db, match.recommended_resume_id)

    return UserJobMatchDetailResponse(
        id=match.id,
        job=JobDetail.model_validate(job),
        job_analysis=JobAnalysisResponse.model_validate(job_analysis) if job_analysis else None,
        skill_match_score=match.skill_match_score,
        skill_match_details=match.skill_match_details,
        resume_match_score=match.resume_match_score,
        resume_match_details=match.resume_match_details,
        recommended_resume=ResumeBriefInfo.model_validate(resume) if resume else None,
        ai_match_score=match.ai_match_score,
        ai_analysis=match.ai_analysis,
        calculated_at=match.calculated_at,
        ai_analyzed_at=match.ai_analyzed_at,
    )


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    keyword: str | None = Query(None, description="Search keyword"),
    location_cities: list[str] | None = Query(None, description="Filter by cities"),
    work_types: list[str] | None = Query(None, description="Filter by work types"),
    companies: list[str] | None = Query(None, description="Filter by companies"),
    sources: list[str] | None = Query(None, description="Filter by sources"),
    view_status: str = Query("all", pattern="^(all|viewed|unviewed)$", description="Viewed status filter"),
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

    return [JobBase.model_validate(job) for job in similar_jobs]


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
    from app.modules.jobs.tasks import analyze_job_task

    job = await JobRepository.get_by_id(db, job_id)
    if not job:
        raise NotFoundError("Job not found")

    task = await TaskService.submit_task(
        db=db,
        task_type=TaskType.JOB_ANALYSIS,
        entity_type=EntityType.job.value,
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
