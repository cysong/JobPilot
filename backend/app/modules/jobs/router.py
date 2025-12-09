"""
Job API endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.jobs import service
from app.modules.jobs.schemas import (
    JobBase,
    JobDetail,
    JobListResponse,
    JobFiltersRequest,
    JobFiltersOptions,
    JobAnalysisResponse,
    UserJobMatchResponse,
    UserJobMatchDetailResponse,
    JobBriefInfo,
    ResumeBriefInfo,
)
from app.shared.pagination import PaginationParams
from app.modules.matching.repository import UserJobMatchRepository
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository
from app.modules.resumes.repository import ResumeRepository

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

    results: list[UserJobMatchResponse] = []
    for match in matches:
        job = await JobRepository.get_by_id(db, match.job_id)
        if not job:
            continue
        resume = None
        if match.recommended_resume_id:
            resume = await ResumeRepository.get_by_id(db, match.recommended_resume_id)

        results.append(
            UserJobMatchResponse(
                id=match.id,
                job=JobBriefInfo.model_validate(job) if job else None,
                skill_match_score=match.skill_match_score,
                resume_match_score=match.resume_match_score,
                ai_match_score=match.ai_match_score,
                recommended_resume=ResumeBriefInfo.model_validate(resume) if resume else None,
                skill_match_details=match.skill_match_details,
                ai_analysis=match.ai_analysis,
                calculated_at=match.calculated_at,
                ai_analyzed_at=match.ai_analyzed_at,
            )
        )

    return results


@router.get("/matches/{job_id}", response_model=UserJobMatchDetailResponse)
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
        raise HTTPException(status_code=404, detail="Match not found")

    job = await JobRepository.get_by_id(db, job_id)
    job_analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not job or not job_analysis:
        raise HTTPException(status_code=404, detail="Job or analysis not found")
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
    listed_after: str | None = Query(None, description="Listed after date (ISO format)"),
    listed_before: str | None = Query(None, description="Listed before date (ISO format)"),
    params: PaginationParams = Depends(),
    sort_by: str = Query("listed_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc")
):
    """
    Get paginated job list with filtering and search.

    - **keyword**: Search in title, abstract, and content
    - **location_cities**: Filter by specific cities
    - **work_types**: Filter by work types (e.g., "Full Time", "Part Time")
    - **companies**: Filter by company names
    - **listed_after/listed_before**: Date range filter
    - **page/page_size** (或 size): Pagination parameters
    - **sort_by/sort_order**: Sorting parameters
    """
    # Parse date strings if provided
    from datetime import datetime
    parsed_listed_after = None
    parsed_listed_before = None

    if listed_after:
        try:
            parsed_listed_after = datetime.fromisoformat(listed_after)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid listed_after date format")

    if listed_before:
        try:
            parsed_listed_before = datetime.fromisoformat(listed_before)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid listed_before date format")

    # Build filter request
    filters = JobFiltersRequest(
        keyword=keyword,
        location_cities=location_cities,
        work_types=work_types,
        companies=companies,
        listed_after=parsed_listed_after,
        listed_before=parsed_listed_before,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Get jobs
    jobs, total = await service.JobService.get_jobs(db, filters, params)

    # Convert to JobBase schema
    job_items = [JobBase.model_validate(job) for job in jobs]

    return JobListResponse.create(
        items=job_items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/filters", response_model=JobFiltersOptions)
async def get_filter_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get available filter options for UI dropdowns.

    Returns distinct values for:
    - location_cities
    - work_types
    - companies
    """
    return await service.JobService.get_filter_options(db)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job_detail(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get detailed job information by ID.
    """
    job = await service.JobService.get_job_by_id(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobDetail.model_validate(job)


@router.get("/{job_id}/similar", response_model=list[JobBase])
async def get_similar_jobs(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(5, ge=1, le=10, description="Number of similar jobs to return")
):
    """
    Get similar jobs from the same company and classification.

    Returns up to `limit` similar jobs, sorted by newest first.
    """
    similar_jobs = await service.JobService.get_similar_jobs(db, job_id, limit)

    return [JobBase.model_validate(job) for job in similar_jobs]


# ============================================
# Job Analysis Endpoints (For Testing)
# ============================================

@router.get("/{job_id}/analysis", response_model=JobAnalysisResponse)
async def get_job_analysis(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get cached job analysis.

    Returns 404 if analysis doesn't exist yet.
    """
    from app.modules.jobs.repository import JobAnalysisRepository

    analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis not found for job {job_id}. Try triggering analysis first."
        )

    return JobAnalysisResponse.model_validate(analysis)


@router.post("/{job_id}/analyze")
async def trigger_job_analysis(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Manually trigger job analysis (test/debug only).

    Returns Celery task ID and task tracking ID.
    """
    from app.modules.jobs.tasks import analyze_job_async
    from app.modules.jobs.repository import JobRepository

    # Verify job exists
    job = await JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Trigger async task
    task = analyze_job_async.delay(job_id)

    return {
        "message": "Analysis triggered",
        "celery_task_id": task.id,
        "job_id": job_id,
    }


@router.delete("/{job_id}/analysis")
async def delete_job_analysis(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Delete cached job analysis (for re-analysis testing).

    Returns 404 if analysis doesn't exist.
    """
    from app.modules.jobs.repository import JobAnalysisRepository

    deleted = await JobAnalysisRepository.delete_by_job_id(db, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis not found")

    await db.commit()

    return {
        "message": f"Analysis for job {job_id} deleted successfully"
    }
