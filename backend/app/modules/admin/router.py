"""Admin router with protected monitoring endpoints."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.dependencies import require_admin
from app.modules.admin.schemas import (
    BatchRetryRequest,
    BatchRetryResponse,
    DashboardStats,
    JobsDailyTrendResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskRetryResponse,
    TaskStatisticsResponse,
    WorkerMonitorResponse,
)
from app.modules.admin.service import AdminService
from app.modules.workflow.service import TaskService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard high-level metrics."""
    return await AdminService.get_dashboard_stats(db)


@router.get("/jobs/daily-trend", response_model=JobsDailyTrendResponse)
async def get_jobs_daily_trend(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Daily new job counts for recent days (grouped by source and total)."""
    return await AdminService.get_jobs_daily_trend(db, days=days)


@router.get("/workers", response_model=WorkerMonitorResponse)
async def get_worker_status():
    """Get real-time status of Celery workers (admin only)."""
    return TaskService.get_worker_status()


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    taskType: Optional[str] = Query(None),
    workerId: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    startTime: Optional[datetime] = Query(None),
    endTime: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    status_filter = status.split(",") if status else None
    return await TaskService.get_tasks(
        db,
        status_filter=status_filter,
        task_type=taskType,
        worker_id=workerId,
        keyword=keyword,
        start_time=startTime,
        end_time=endTime,
        page=page,
        page_size=pageSize,
    )


@router.get("/tasks/statistics", response_model=TaskStatisticsResponse)
async def task_statistics(
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    taskType: Optional[str] = Query(None),
    startTime: Optional[datetime] = Query(None),
    endTime: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    status_filter = status.split(",") if status else None
    return await TaskService.get_task_statistics(
        db,
        status_filter=status_filter,
        task_type=taskType,
        start_time=startTime,
        end_time=endTime,
    )

@router.post("/tasks/batch-retry", response_model=BatchRetryResponse)
async def batch_retry(payload: BatchRetryRequest, db: AsyncSession = Depends(get_db)):
    """Batch retry tasks."""
    return await TaskService.batch_retry_tasks(db, payload.task_ids)

@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get task details (with AI calls)."""
    return await TaskService.get_task_detail(db, task_id)


@router.post("/tasks/{task_id}/retry", response_model=TaskRetryResponse)
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Retry a single task."""
    return await TaskService.retry_task(db, task_id)
