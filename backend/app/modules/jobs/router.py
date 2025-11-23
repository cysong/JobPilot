"""
Job API endpoints.
"""
import math
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
    JobFiltersOptions
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
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
    - **page/page_size**: Pagination parameters
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
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Get jobs
    jobs, total = await service.JobService.get_jobs(db, filters)

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Convert to JobBase schema
    job_items = [JobBase.model_validate(job) for job in jobs]

    return JobListResponse(
        items=job_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
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
