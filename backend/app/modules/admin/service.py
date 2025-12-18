"""Business logic for admin dashboard/monitoring endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.schemas import DashboardStats, MetricCount, TaskMetric
from app.modules.applications.models import Application
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.matching.models import UserJobMatch
from app.modules.workflow.models import TaskExecution
from app.shared.enums import TaskStatus


class AdminService:
    """Service methods for admin dashboard metrics."""

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
        """Aggregate high-level metrics for dashboard."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        users_total = await db.scalar(select(func.count(User.id)))
        users_today = await db.scalar(select(func.count(User.id)).where(User.created_at >= today_start))

        jobs_total = await db.scalar(select(func.count(SeekJob.id)))
        jobs_today = await db.scalar(
            select(func.count(SeekJob.id)).where(SeekJob.created_at.isnot(None)).where(SeekJob.created_at >= today_start)
        )

        matches_total = await db.scalar(select(func.count(UserJobMatch.id)))
        matches_today = await db.scalar(select(func.count(UserJobMatch.id)).where(UserJobMatch.created_at >= today_start))

        applications_total = await db.scalar(select(func.count(Application.id)).where(Application.is_deleted.is_(False)))
        applications_today = await db.scalar(
            select(func.count(Application.id)).where(Application.is_deleted.is_(False)).where(
                Application.created_at >= today_start
            )
        )

        tasks_total = await db.scalar(select(func.count(TaskExecution.id)))
        tasks_today = await db.scalar(select(func.count(TaskExecution.id)).where(TaskExecution.created_at >= today_start))
        tasks_running = await db.scalar(
            select(func.count(TaskExecution.id)).where(TaskExecution.status == TaskStatus.RUNNING)
        )
        tasks_failed = await db.scalar(
            select(func.count(TaskExecution.id)).where(TaskExecution.status == TaskStatus.FAILED)
        )

        return DashboardStats(
            users=MetricCount(total=users_total or 0, today_new=users_today or 0),
            jobs=MetricCount(total=jobs_total or 0, today_new=jobs_today or 0),
            matches=MetricCount(total=matches_total or 0, today_new=matches_today or 0),
            applications=MetricCount(total=applications_total or 0, today_new=applications_today or 0),
            tasks=TaskMetric(
                total=tasks_total or 0,
                today_new=tasks_today or 0,
                running=tasks_running or 0,
                failed=tasks_failed or 0,
            ),
        )
