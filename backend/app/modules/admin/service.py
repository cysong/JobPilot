"""Business logic for admin dashboard/monitoring endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.admin.schemas import DashboardStats, MetricCount, TaskMetric
from app.modules.applications.models import Application
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.matching.models import UserJobMatch
from app.modules.workflow.models import TaskExecution
from app.shared.enums import TaskStatus
from app.core.cache import jcache


class AdminService:
    """Service methods for admin dashboard metrics."""

    @staticmethod
    def _today_start_utc() -> datetime:
        """Return local-day start converted to UTC for consistent DB filtering."""
        try:
            app_tz = ZoneInfo(settings.APP_TIMEZONE)
        except ZoneInfoNotFoundError:
            app_tz = timezone.utc

        now_local = datetime.now(app_tz)
        today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start_local.astimezone(timezone.utc)

    @staticmethod
    @jcache("admin:dashboard:stats", ttl=300)
    async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
        """Aggregate high-level metrics for dashboard."""
        today_start = AdminService._today_start_utc()

        users_total, users_today = (
            await db.execute(
                select(
                    func.count(User.id),
                    func.count(User.id).filter(User.created_at >= today_start),
                )
            )
        ).one()

        jobs_total, jobs_today = (
            await db.execute(
                select(
                    func.count(SeekJob.id),
                    func.count(SeekJob.id).filter(SeekJob.created_at >= today_start),
                )
            )
        ).one()

        matches_total, matches_today = (
            await db.execute(
                select(
                    func.count(UserJobMatch.id),
                    func.count(UserJobMatch.id).filter(UserJobMatch.created_at >= today_start),
                )
            )
        ).one()

        applications_total, applications_today = (
            await db.execute(
                select(
                    func.count(Application.id).filter(Application.is_deleted.is_(False)),
                    func.count(Application.id).filter(
                        Application.is_deleted.is_(False),
                        Application.created_at >= today_start,
                    ),
                )
            )
        ).one()

        tasks_total, tasks_today, tasks_running, tasks_failed = (
            await db.execute(
                select(
                    func.count(TaskExecution.id),
                    func.count(TaskExecution.id).filter(TaskExecution.created_at >= today_start),
                    func.count(TaskExecution.id).filter(TaskExecution.status == TaskStatus.RUNNING),
                    func.count(TaskExecution.id).filter(TaskExecution.status == TaskStatus.FAILED),
                )
            )
        ).one()

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
