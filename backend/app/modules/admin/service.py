"""Business logic for admin dashboard/monitoring endpoints."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.admin.schemas import (
    DashboardStats,
    JobsDailyTrendPoint,
    JobsDailyTrendResponse,
    JobsDailyTrendSeries,
    MetricCount,
    TaskMetric,
)
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

    @staticmethod
    @jcache("admin:jobs:daily-trend:{days}", ttl=300)
    async def get_jobs_daily_trend(db: AsyncSession, days: int = 30) -> JobsDailyTrendResponse:
        """Return daily new job counts for recent days by source and total."""
        days = max(7, min(days, 90))

        try:
            app_tz = ZoneInfo(settings.APP_TIMEZONE)
            tz_name = settings.APP_TIMEZONE
        except ZoneInfoNotFoundError:
            app_tz = timezone.utc
            tz_name = "UTC"

        today_local = datetime.now(app_tz).date()
        start_date = today_local - timedelta(days=days - 1)
        end_date = today_local

        start_local_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=app_tz)
        end_exclusive_local_dt = datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=app_tz
        )

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        source_name = func.coalesce(func.nullif(func.trim(SeekJob.source), ""), "Unknown")
        local_date = cast(func.timezone(tz_name, SeekJob.created_at), Date)

        rows = (
            await db.execute(
                select(
                    local_date.label("local_date"),
                    source_name.label("source_name"),
                    func.count(SeekJob.id).label("job_count"),
                )
                .where(
                    SeekJob.created_at.isnot(None),
                    SeekJob.created_at >= start_utc,
                    SeekJob.created_at < end_exclusive_utc,
                )
                .group_by("local_date", "source_name")
                .order_by("local_date", "source_name")
            )
        ).all()

        by_source_and_date: dict[str, dict[date, int]] = {}
        all_sources: set[str] = set()

        for local_day, source, count in rows:
            if local_day is None:
                continue
            source_key = str(source)
            all_sources.add(source_key)
            by_source_and_date.setdefault(source_key, {})[local_day] = int(count or 0)

        sorted_sources = sorted(all_sources)
        dates = [start_date + timedelta(days=i) for i in range(days)]

        series: list[JobsDailyTrendSeries] = []

        total_points: list[JobsDailyTrendPoint] = []
        for day in dates:
            total_count = sum(by_source_and_date.get(source, {}).get(day, 0) for source in sorted_sources)
            total_points.append(JobsDailyTrendPoint(date=day.isoformat(), count=total_count))
        series.append(JobsDailyTrendSeries(name="Total", points=total_points))

        for source in sorted_sources:
            points = [
                JobsDailyTrendPoint(
                    date=day.isoformat(),
                    count=by_source_and_date.get(source, {}).get(day, 0),
                )
                for day in dates
            ]
            series.append(JobsDailyTrendSeries(name=source, points=points))

        return JobsDailyTrendResponse(
            timezone=tz_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            sources=sorted_sources,
            series=series,
        )
