"""Business logic for admin dashboard/monitoring endpoints."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.admin.schemas import (
    AIUsageDailyTrendPoint,
    AIUsageDailyTrendResponse,
    AIUsageDailyTrendSeries,
    DashboardStats,
    FloatMetricCount,
    JobsDailyTrendPoint,
    JobsDailyTrendResponse,
    JobsDailyTrendSeries,
    JobsTimeScatterPoint,
    JobsTimeScatterResponse,
    MetricCount,
    TaskMetric,
    TasksDailyTrendPoint,
    TasksDailyTrendResponse,
    TasksDailyTrendSeries,
    TasksExecutionTimePoint,
    TasksExecutionTimeResponse,
    TasksExecutionTimeSeries,
)
from app.modules.applications.models import Application
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.matching.models import UserJobMatch
from app.modules.workflow.models import AICall, TaskExecution
from app.shared.enums import TaskStatus
from app.core.cache import jcache


class AdminService:
    """Service methods for admin dashboard metrics."""

    @staticmethod
    def _app_timezone() -> tuple[timezone | ZoneInfo, str]:
        """Return configured app timezone and fallback-safe name."""
        try:
            return ZoneInfo(settings.APP_TIMEZONE), settings.APP_TIMEZONE
        except ZoneInfoNotFoundError:
            return timezone.utc, "UTC"

    @staticmethod
    def _today_start_utc() -> datetime:
        """Return local-day start converted to UTC for consistent DB filtering."""
        app_tz, _ = AdminService._app_timezone()

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

        ai_tokens_total, ai_tokens_today, ai_cost_total, ai_cost_today = (
            await db.execute(
                select(
                    func.coalesce(func.sum(AICall.total_tokens), 0),
                    func.coalesce(
                        func.sum(AICall.total_tokens).filter(AICall.created_at >= today_start),
                        0,
                    ),
                    func.coalesce(func.sum(AICall.estimated_cost), 0.0),
                    func.coalesce(
                        func.sum(AICall.estimated_cost).filter(AICall.created_at >= today_start),
                        0.0,
                    ),
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
            ai_tokens=MetricCount(
                total=int(ai_tokens_total or 0),
                today_new=int(ai_tokens_today or 0),
            ),
            ai_cost=FloatMetricCount(
                total=float(ai_cost_total or 0.0),
                today_new=float(ai_cost_today or 0.0),
            ),
        )

    @staticmethod
    @jcache("admin:jobs:daily-trend:{days}", ttl=300)
    async def get_jobs_daily_trend(db: AsyncSession, days: int = 30) -> JobsDailyTrendResponse:
        """Return daily new job counts for recent days by source and total."""
        days = max(7, min(days, 90))

        app_tz, tz_name = AdminService._app_timezone()

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

    @staticmethod
    @jcache("admin:jobs:time-scatter:{days}", ttl=300)
    async def get_jobs_time_scatter(db: AsyncSession, days: int = 30) -> JobsTimeScatterResponse:
        """Return hourly local-time job counts by source for scatter plotting."""
        days = max(1, min(days, 90))
        bucket_minutes = 60
        app_tz, tz_name = AdminService._app_timezone()

        end_local_dt = datetime.now(app_tz).replace(minute=0, second=0, microsecond=0)
        start_local_dt = end_local_dt - timedelta(hours=(days * 24) - 1)
        end_exclusive_local_dt = end_local_dt + timedelta(hours=1)

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        source_name = func.coalesce(func.nullif(func.trim(SeekJob.source), ""), "Unknown")
        local_bucket = func.date_trunc("hour", func.timezone(tz_name, SeekJob.created_at))

        rows = (
            await db.execute(
                select(
                    local_bucket.label("local_bucket"),
                    source_name.label("source_name"),
                    func.count(SeekJob.id).label("job_count"),
                )
                .where(
                    SeekJob.created_at.isnot(None),
                    SeekJob.created_at >= start_utc,
                    SeekJob.created_at < end_exclusive_utc,
                )
                .group_by("local_bucket", "source_name")
                .order_by("local_bucket", "source_name")
            )
        ).all()

        points: list[JobsTimeScatterPoint] = []
        all_sources: set[str] = set()

        for local_bucket_value, source, count in rows:
            if local_bucket_value is None:
                continue

            source_key = str(source)
            all_sources.add(source_key)
            aware_local_bucket = local_bucket_value.replace(tzinfo=app_tz)
            points.append(
                JobsTimeScatterPoint(
                    bucket_start=aware_local_bucket,
                    source=source_key,
                    count=int(count or 0),
                )
            )

        return JobsTimeScatterResponse(
            timezone=tz_name,
            bucket_minutes=bucket_minutes,
            start_date_time=start_local_dt,
            end_date_time=end_local_dt,
            sources=sorted(all_sources),
            points=points,
        )

    @staticmethod
    async def _get_ai_usage_daily_trend(
        db: AsyncSession,
        days: int,
        metric_expr,
    ) -> AIUsageDailyTrendResponse:
        """Return daily AI usage totals and per-model series."""
        days = max(7, min(days, 90))
        app_tz, tz_name = AdminService._app_timezone()

        today_local = datetime.now(app_tz).date()
        start_date = today_local - timedelta(days=days - 1)
        end_date = today_local

        start_local_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=app_tz)
        end_exclusive_local_dt = datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=app_tz
        )

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        model_name = func.coalesce(func.nullif(func.trim(AICall.model), ""), "Unknown")
        local_date = cast(func.timezone(tz_name, AICall.created_at), Date)

        rows = (
            await db.execute(
                select(
                    local_date.label("local_date"),
                    model_name.label("model_name"),
                    func.coalesce(func.sum(metric_expr), 0).label("metric_value"),
                )
                .where(
                    AICall.created_at.isnot(None),
                    AICall.created_at >= start_utc,
                    AICall.created_at < end_exclusive_utc,
                )
                .group_by("local_date", "model_name")
                .order_by("local_date", "model_name")
            )
        ).all()

        by_model_and_date: dict[str, dict[date, float]] = {}
        all_models: set[str] = set()

        for local_day, model, value in rows:
            if local_day is None:
                continue
            model_key = str(model)
            all_models.add(model_key)
            by_model_and_date.setdefault(model_key, {})[local_day] = float(value or 0)

        sorted_models = sorted(all_models)
        dates = [start_date + timedelta(days=i) for i in range(days)]

        series: list[AIUsageDailyTrendSeries] = []

        total_points: list[AIUsageDailyTrendPoint] = []
        for day in dates:
            total_value = sum(by_model_and_date.get(model, {}).get(day, 0) for model in sorted_models)
            total_points.append(AIUsageDailyTrendPoint(date=day.isoformat(), value=total_value))
        series.append(AIUsageDailyTrendSeries(name="Total", points=total_points))

        for model in sorted_models:
            points = [
                AIUsageDailyTrendPoint(
                    date=day.isoformat(),
                    value=by_model_and_date.get(model, {}).get(day, 0),
                )
                for day in dates
            ]
            series.append(AIUsageDailyTrendSeries(name=model, points=points))

        return AIUsageDailyTrendResponse(
            timezone=tz_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            models=sorted_models,
            series=series,
        )

    @staticmethod
    @jcache("admin:ai:tokens-daily-trend:{days}", ttl=300)
    async def get_ai_tokens_daily_trend(
        db: AsyncSession,
        days: int = 30,
    ) -> AIUsageDailyTrendResponse:
        """Return daily token consumption totals and per-model series."""
        return await AdminService._get_ai_usage_daily_trend(db, days, AICall.total_tokens)

    @staticmethod
    @jcache("admin:ai:cost-daily-trend:{days}", ttl=300)
    async def get_ai_cost_daily_trend(
        db: AsyncSession,
        days: int = 30,
    ) -> AIUsageDailyTrendResponse:
        """Return daily estimated USD cost totals and per-model series."""
        return await AdminService._get_ai_usage_daily_trend(db, days, AICall.estimated_cost)

    @staticmethod
    @jcache("admin:tasks:daily-trend:{days}", ttl=300)
    async def get_tasks_daily_trend(db: AsyncSession, days: int = 30) -> TasksDailyTrendResponse:
        """Return daily task counts and failed counts per task_name, plus a Total series.

        Buckets by user's app timezone. ``failure_rate`` is ``None`` when count is 0
        so the frontend can break failure-rate lines at empty days. The ``Total``
        series sums across all task types and exposes the overall failure rate.
        """
        days = max(7, min(days, 90))

        app_tz, tz_name = AdminService._app_timezone()

        today_local = datetime.now(app_tz).date()
        start_date = today_local - timedelta(days=days - 1)
        end_date = today_local

        start_local_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=app_tz)
        end_exclusive_local_dt = datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=app_tz
        )

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        local_date = cast(func.timezone(tz_name, TaskExecution.created_at), Date)
        failed_expr = case((TaskExecution.status == TaskStatus.FAILED, 1), else_=0)

        rows = (
            await db.execute(
                select(
                    local_date.label("local_date"),
                    TaskExecution.task_name.label("task_name"),
                    func.count(TaskExecution.id).label("task_count"),
                    func.coalesce(func.sum(failed_expr), 0).label("failed_count"),
                )
                .where(
                    TaskExecution.created_at.isnot(None),
                    TaskExecution.created_at >= start_utc,
                    TaskExecution.created_at < end_exclusive_utc,
                )
                .group_by("local_date", "task_name")
                .order_by("local_date", "task_name")
            )
        ).all()

        # by_type[task_name][date] -> (count, failed)
        by_type: dict[str, dict[date, tuple[int, int]]] = {}
        all_types: set[str] = set()

        for local_day, task_name, task_count, failed_count in rows:
            if local_day is None or not task_name:
                continue
            name = str(task_name)
            all_types.add(name)
            by_type.setdefault(name, {})[local_day] = (
                int(task_count or 0),
                int(failed_count or 0),
            )

        sorted_types = sorted(all_types)
        dates = [start_date + timedelta(days=i) for i in range(days)]

        def make_point(count: int, failed: int, day: date) -> TasksDailyTrendPoint:
            rate = (failed / count) if count > 0 else None
            return TasksDailyTrendPoint(
                date=day.isoformat(),
                count=count,
                failed=failed,
                failure_rate=rate,
            )

        series: list[TasksDailyTrendSeries] = []

        total_points: list[TasksDailyTrendPoint] = []
        for day in dates:
            day_count = 0
            day_failed = 0
            for name in sorted_types:
                count, failed = by_type.get(name, {}).get(day, (0, 0))
                day_count += count
                day_failed += failed
            total_points.append(make_point(day_count, day_failed, day))
        series.append(TasksDailyTrendSeries(name="Total", points=total_points))

        for name in sorted_types:
            points = []
            for day in dates:
                count, failed = by_type.get(name, {}).get(day, (0, 0))
                points.append(make_point(count, failed, day))
            series.append(TasksDailyTrendSeries(name=name, points=points))

        return TasksDailyTrendResponse(
            timezone=tz_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            task_types=sorted_types,
            series=series,
        )

    @staticmethod
    @jcache("admin:tasks:execution-time:{days}", ttl=300)
    async def get_tasks_execution_time(db: AsyncSession, days: int = 30) -> TasksExecutionTimeResponse:
        """Return per-day avg/p50/p95 execution_time_ms grouped by task_name.

        Only ``status = SUCCESS`` rows contribute; failed tasks have unreliable
        durations. A ``(date, task_name)`` cell with no successful samples is
        omitted from that series' points — the frontend uses ``connectNulls=false``
        to break the line at the gap.
        """
        days = max(7, min(days, 90))

        app_tz, tz_name = AdminService._app_timezone()

        today_local = datetime.now(app_tz).date()
        start_date = today_local - timedelta(days=days - 1)
        end_date = today_local

        start_local_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=app_tz)
        end_exclusive_local_dt = datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=app_tz
        )

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        local_date = cast(func.timezone(tz_name, TaskExecution.created_at), Date)
        duration = TaskExecution.execution_time_ms

        rows = (
            await db.execute(
                select(
                    local_date.label("local_date"),
                    TaskExecution.task_name.label("task_name"),
                    func.avg(duration).label("avg_ms"),
                    func.percentile_cont(0.5).within_group(duration.asc()).label("p50_ms"),
                    func.percentile_cont(0.95).within_group(duration.asc()).label("p95_ms"),
                    func.count(TaskExecution.id).label("sample_count"),
                )
                .where(
                    TaskExecution.created_at.isnot(None),
                    TaskExecution.created_at >= start_utc,
                    TaskExecution.created_at < end_exclusive_utc,
                    TaskExecution.status == TaskStatus.SUCCESS,
                    TaskExecution.execution_time_ms.isnot(None),
                )
                .group_by("local_date", "task_name")
                .order_by("local_date", "task_name")
            )
        ).all()

        # by_type[task_name] -> list of points (chronological)
        by_type: dict[str, list[TasksExecutionTimePoint]] = {}
        all_types: set[str] = set()

        for local_day, task_name, avg_ms, p50_ms, p95_ms, sample_count in rows:
            if local_day is None or not task_name:
                continue
            name = str(task_name)
            all_types.add(name)
            by_type.setdefault(name, []).append(
                TasksExecutionTimePoint(
                    date=local_day.isoformat(),
                    avg_ms=float(avg_ms),
                    p50_ms=float(p50_ms),
                    p95_ms=float(p95_ms),
                    sample_count=int(sample_count or 0),
                )
            )

        sorted_types = sorted(all_types)

        series: list[TasksExecutionTimeSeries] = [
            TasksExecutionTimeSeries(name=name, points=by_type.get(name, []))
            for name in sorted_types
        ]

        return TasksExecutionTimeResponse(
            timezone=tz_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            task_types=sorted_types,
            series=series,
        )
