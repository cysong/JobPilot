"""Task submission and task management service (single-table task model)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any, Iterable, Optional
from uuid import uuid4

from celery import chain
from sqlalchemy import and_, or_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, JobPilotException, NotFoundError

from app.modules.admin.schemas import (
    BatchRetryResponse,
    BatchRetryResult,
    TaskDetailResponse,
    TaskListItem,
    TaskListResponse,
    TaskListStats,
    TaskRetryResponse,
    TaskStatisticsResponse,
    TaskTypeStats,
    WorkerMonitorResponse,
    WorkerStatus,
)
from app.modules.workflow.models import TaskExecution, AICall
from app.modules.workflow.repositories import TaskRepository
from app.shared.enums import TaskStatus, TaskType, TaskTypeInfo

logger = logging.getLogger(__name__)


@dataclass
class TaskSubmissionSpec:
    """Spec for a single task in a sequential chain."""

    task_type: TaskType
    input_data: Optional[dict] = field(default_factory=dict)
    celery_kwargs: Optional[dict] = field(default_factory=dict)
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None


class TaskService:
    """Create, inspect, and manage tracked tasks."""

    @staticmethod
    async def submit_task(
        db: AsyncSession,
        *,
        task_type: TaskType,
        entity_type: Optional[str] = None,
        entity_id: str,
        user_id: int | None = None,
        input_data: Optional[dict] = None,
        workflow_id: str | None = None,
        depends_on: Optional[list[str]] = None,
        **celery_kwargs: Any,
    ) -> TaskExecution:
        """
        Create a task_executions row and dispatch Celery task.

        If workflow_id is not provided, a single-task workflow uses task_id as workflow_id.
        """
        info: TaskTypeInfo = task_type.value
        task_id = str(uuid4())
        workflow_id = workflow_id or task_id

        task = await TaskRepository.create(
            db=db,
            id=task_id,
            workflow_id=workflow_id,
            entity_type=entity_type or info.entity,
            entity_id=entity_id,
            user_id=user_id,
            task_type=info.value,
            task_name=info.display_name,
            input_data=input_data or {},
            step=1,
            total_steps=1,
            depends_on=depends_on,
        )
        await db.flush()
        await db.commit()

        module_path, func_name = info.celery_task.rsplit(".", 1)
        module = import_module(module_path)
        celery_task = getattr(module, func_name)

        task_kwargs = {
            "task_id": task_id,
            **(input_data or {}),
        }

        # Create signature to properly set task options
        sig = celery_task.signature(kwargs=task_kwargs)

        # Set retry and timeout configurations via signature.set()
        if info.max_retries is not None:
            sig.set(max_retries=info.max_retries)
        if info.timeout_seconds is not None:
            sig.set(time_limit=info.timeout_seconds)
        if celery_kwargs:
            sig.set(**celery_kwargs)

        async_result = sig.apply_async()
        task.celery_task_id = async_result.id
        await db.commit()

        logger.info(
            "task_submitted_to_celery",
            extra={
                "workflow_id": workflow_id,
                "task_id": task_id,
                "task_type": info.value,
                "celery_task_id": async_result.id,
            },
        )

        return task

    @staticmethod
    async def submit_sequential_tasks(
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        user_id: int | None,
        tasks: list[TaskSubmissionSpec],
        workflow_id: str | None = None,
    ) -> list[TaskExecution]:
        """
        Create tasks in order and dispatch via Celery chain to enforce sequencing.

        Args:
            db: AsyncSession
            entity_type: business entity type (job/resume/application)
            entity_id: business entity id
            user_id: optional user id
            tasks: ordered list of task specifications
            workflow_id: optional workflow id (defaults to first task id)
        """
        if not tasks:
            raise ValueError("tasks list cannot be empty")

        workflow_id = workflow_id or str(uuid4())
        created: list[TaskExecution] = []
        signatures = []
        prev_task_id: str | None = None
        total_steps = len(tasks)

        for idx, spec in enumerate(tasks, start=1):
            info: TaskTypeInfo = spec.task_type.value
            task_id = str(uuid4())
            task = await TaskRepository.create(
                db=db,
                id=task_id,
                workflow_id=workflow_id,
                entity_type=spec.entity_type or info.entity or entity_type,
                entity_id=spec.entity_id or entity_id,
                user_id=user_id,
                task_type=info.value,
                task_name=info.display_name,
                input_data=spec.input_data or {},
                step=idx,
                total_steps=total_steps,
                depends_on=[prev_task_id] if prev_task_id else None,
            )
            await db.flush()
            created.append(task)

            module_path, func_name = info.celery_task.rsplit(".", 1)
            module = import_module(module_path)
            celery_task = getattr(module, func_name)

            task_kwargs = {"task_id": task_id}
            task_kwargs.update(spec.input_data or {})

            # Use immutable signature to avoid previous result being injected as first arg in chain
            sig = celery_task.si(**task_kwargs)
            if info.max_retries is not None:
                sig.set(max_retries=info.max_retries)
            if info.timeout_seconds is not None:
                sig.set(time_limit=info.timeout_seconds)
            if spec.celery_kwargs:
                sig.set(**spec.celery_kwargs)

            signatures.append(sig)
            prev_task_id = task_id

        await db.commit()

        chain_result = chain(*signatures).apply_async()

        # Propagate Celery task IDs back to TaskExecution records (walk parents)
        current_result = chain_result
        for task in reversed(created):
            task.celery_task_id = getattr(current_result, "id", None)
            current_result = getattr(current_result, "parent", None)
        await db.commit()

        logger.info(
            "sequential_tasks_submitted",
            extra={
                "workflow_id": workflow_id,
                "task_ids": [t.id for t in created],
                "task_types": [t.task_type for t in created],
            },
        )

        return created


    @staticmethod
    def get_worker_status() -> WorkerMonitorResponse:
        """Return worker status and queue stats via Celery inspect."""
        from app.core.celery_app import celery_app  # local import to avoid circular import during app bootstrap
        inspector = celery_app.control.inspect()

        ping = inspector.ping() or {}
        stats = inspector.stats() or {}
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        scheduled = inspector.scheduled() or {}

        if not ping and not stats and not active and not reserved and not scheduled:
            return WorkerMonitorResponse(active_count=0, queued_tasks=0, running_tasks=0, workers=[])

        worker_names = set()
        worker_names.update(ping.keys())
        worker_names.update(stats.keys())
        worker_names.update(active.keys())
        worker_names.update(reserved.keys())
        worker_names.update(scheduled.keys())

        workers: list[WorkerStatus] = []
        active_count = 0
        queued_tasks = 0
        running_tasks = 0

        for worker_name in worker_names:
            stats_data = stats.get(worker_name) or {}
            is_online = worker_name in ping or bool(stats_data)
            if is_online:
                active_count += 1

            current = len(active.get(worker_name, []))
            queued = len(reserved.get(worker_name, [])) + len(scheduled.get(worker_name, []))
            running_tasks += current
            queued_tasks += queued

            last_hb_raw = stats_data.get("heartbeat")
            last_heartbeat_dt = None
            if isinstance(last_hb_raw, (int, float)):
                last_heartbeat_dt = datetime.fromtimestamp(last_hb_raw, timezone.utc)

            workers.append(
                WorkerStatus(
                    id=worker_name,
                    hostname=stats_data.get("hostname") or worker_name,
                    status="active" if is_online else "offline",
                    current_tasks=current,
                    last_heartbeat=last_heartbeat_dt,
                )
            )

        return WorkerMonitorResponse(
            active_count=active_count,
            queued_tasks=queued_tasks,
            running_tasks=running_tasks,
            workers=workers,
        )

    @staticmethod
    def _is_task_id_in_broker(celery_task_id: str) -> bool:
        """
        Check whether a Celery task ID is currently visible in worker snapshots.

        This avoids building a full in-memory task-id set when we only need
        to validate one specific task.
        """
        if not celery_task_id:
            return False

        from app.core.celery_app import celery_app

        inspector = celery_app.control.inspect()

        def _extract_task_id(item: Any) -> str | None:
            if not isinstance(item, dict):
                return None

            direct_id = item.get("id")
            if isinstance(direct_id, str) and direct_id:
                return direct_id

            request = item.get("request")
            if isinstance(request, dict):
                request_id = request.get("id")
                if isinstance(request_id, str) and request_id:
                    return request_id

            return None

        for snapshot in (inspector.active() or {}, inspector.reserved() or {}, inspector.scheduled() or {}):
            for items in snapshot.values():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if _extract_task_id(item) == celery_task_id:
                        return True

        return False

    @staticmethod
    def _is_task_stale(task: TaskExecution, now: datetime) -> bool:
        """Return True when pending/running task exceeds stale timeout."""
        timeout = timedelta(minutes=settings.TASK_RETRY_STALE_TIMEOUT_MINUTES)

        if task.status == TaskStatus.PENDING:
            reference_time = task.created_at
        elif task.status == TaskStatus.RUNNING:
            reference_time = task.started_at or task.created_at
        else:
            return False

        if reference_time is None:
            return False
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        return reference_time <= (now - timeout)

    @staticmethod
    def _can_retry_anchor_task(
        task: TaskExecution,
        *,
        now: datetime,
    ) -> tuple[bool, str]:
        """
        Decide if the workflow anchor task can be manually retried.

        Allowed:
        - FAILED tasks
        - PENDING/RUNNING tasks that are stale and no longer present in broker snapshot
        """
        if task.status == TaskStatus.FAILED:
            return True, "failed"

        if task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
            if not TaskService._is_task_stale(task, now):
                return (
                    False,
                    f"Task {task.id} is {task.status.value} but not stale enough for retry "
                    f"(threshold: {settings.TASK_RETRY_STALE_TIMEOUT_MINUTES} minutes).",
                )

            if task.celery_task_id and TaskService._is_task_id_in_broker(task.celery_task_id):
                return (
                    False,
                    f"Task {task.id} is still present in broker queues/active workers "
                    f"(celery_task_id={task.celery_task_id}).",
                )

            return True, "stale_no_broker_presence"

        return (
            False,
            f"Task {task.id} in status {task.status.value} is not eligible for manual retry.",
        )

    @staticmethod
    async def get_tasks(
        db: AsyncSession,
        *,
        status_filter: Optional[list[str]] = None,
        task_type: Optional[str] = None,
        worker_id: Optional[str] = None,
        keyword: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> TaskListResponse:
        """List tasks with filters and pagination."""
        filters = []
        if status_filter:
            filters.append(TaskExecution.status.in_(status_filter))
        if task_type:
            filters.append(TaskExecution.task_type == task_type)
        if worker_id:
            filters.append(TaskExecution.worker_id == worker_id)
        if keyword:
            like = f"%{keyword}%"
            filters.append(
                or_(
                    TaskExecution.id == keyword,
                    TaskExecution.workflow_id == keyword,
                    TaskExecution.entity_id == keyword,
                    TaskExecution.task_name.ilike(like),
                )
            )
        if start_time:
            filters.append(TaskExecution.created_at >= start_time)
        if end_time:
            filters.append(TaskExecution.created_at <= end_time)

        base_query = select(TaskExecution).where(and_(*filters)) if filters else select(TaskExecution)
        total = await db.scalar(select(func.count()).select_from(base_query.subquery()))

        stmt = base_query.order_by(TaskExecution.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
        task_ids = [t.id for t in rows]

        ai_cost_map = {}
        if task_ids:
            cost_rows = await db.execute(
                select(AICall.task_id, func.coalesce(func.sum(AICall.estimated_cost), 0))
                .where(AICall.task_id.in_(task_ids))
                .group_by(AICall.task_id)
            )
            ai_cost_map = {task_id: cost for task_id, cost in cost_rows.all()}

        now = datetime.now(timezone.utc)
        timeout_threshold = now - timedelta(minutes=settings.TASK_RETRY_STALE_TIMEOUT_MINUTES)

        items = []
        for task in rows:
            items.append(
                TaskListItem(
                    id=task.id,
                    task_name=task.task_name,
                    task_type=task.task_type,
                    status=task.status,
                    worker_id=task.worker_id,
                    celery_task_id=task.celery_task_id,
                    retry_count=task.retry_count,
                    max_retries=task.max_retries,
                    execution_time_ms=task.execution_time_ms,
                    error_message=task.error_message,
                    ai_cost=float(ai_cost_map.get(task.id, 0) or 0),
                    entity_type=task.entity_type,
                    entity_id=task.entity_id,
                    user_id=task.user_id,
                    workflow_id=task.workflow_id,
                    created_at=task.created_at,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                )
            )

        filtered_sub = base_query.subquery()
        status_counts = await db.execute(
            select(filtered_sub.c.status, func.count().label("cnt")).group_by(filtered_sub.c.status)
        )
        status_map = {row[0]: row[1] for row in status_counts.all()}

        task_type_counts = await db.execute(
            select(filtered_sub.c.task_type, func.count()).group_by(filtered_sub.c.task_type)
        )
        type_map = {row[0]: row[1] for row in task_type_counts.all() if row[0]}

        timeout_count = await db.scalar(
            select(func.count()).select_from(filtered_sub).where(
                filtered_sub.c.status == TaskStatus.RUNNING,
                filtered_sub.c.started_at.isnot(None),
                filtered_sub.c.started_at < timeout_threshold,
            )
        ) or 0

        stats = TaskListStats(
            failed=int(status_map.get(TaskStatus.FAILED, 0)),
            timeout=int(timeout_count),
            success=int(status_map.get(TaskStatus.SUCCESS, 0)),
            running=int(status_map.get(TaskStatus.RUNNING, 0)),
            task_type_distribution=type_map,
        )

        total_pages = (total + page_size - 1) // page_size if total else 0

        return TaskListResponse(
            items=items,
            total=int(total or 0),
            page=page,
            page_size=page_size,
            total_pages=int(total_pages),
            stats=stats,
        )

    @staticmethod
    async def get_task_detail(db: AsyncSession, task_id: str) -> TaskDetailResponse:
        """Get single task detail including AI calls."""
        task = await db.get(TaskExecution, task_id)
        if not task:
            raise NotFoundError("Task not found")

        ai_calls = await db.execute(
            select(AICall).where(AICall.task_id == task_id).order_by(AICall.created_at.desc())
        )
        ai_call_items = [
            {
                "id": ac.id,
                "model": ac.model,
                "model_provider": ac.model_provider,
                "agent_id": ac.agent_id,
                "input_tokens": ac.input_tokens,
                "output_tokens": ac.output_tokens,
                "total_tokens": ac.total_tokens,
                "estimated_cost": ac.estimated_cost,
                "latency_ms": ac.latency_ms,
                "status": ac.status,
                "error_message": ac.error_message,
                "metadata": ac.metadata_,
                "created_at": ac.created_at,
            }
            for ac in ai_calls.scalars().all()
        ]

        return TaskDetailResponse(
            id=task.id,
            task_name=task.task_name,
            task_type=task.task_type,
            status=task.status,
            worker_id=task.worker_id,
            celery_task_id=task.celery_task_id,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            execution_time_ms=task.execution_time_ms,
            error_message=task.error_message,
            input_data=task.input_data,
            output_data=task.output_data,
            entity_type=task.entity_type,
            entity_id=task.entity_id,
            user_id=task.user_id,
            workflow_id=task.workflow_id,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            ai_calls=ai_call_items,
        )

    @staticmethod
    async def retry_task(db: AsyncSession, task_id: str) -> TaskRetryResponse:
        """
        Retry starting from the first non-success task in the workflow.

        Resets retry_count to 0 and resubmits the remaining tasks in order via Celery chain.
        """
        original = await db.get(TaskExecution, task_id)
        if not original:
            raise NotFoundError("Task not found")

        # Fetch workflow tasks in order
        workflow_tasks = (
            await db.execute(
                select(TaskExecution)
                .where(TaskExecution.workflow_id == original.workflow_id)
                .order_by(TaskExecution.step.asc())
            )
        ).scalars().all()
        if not workflow_tasks:
            raise NotFoundError("No tasks found for workflow")

        # Find first non-success task and retry everything from there
        start_idx = next((idx for idx, t in enumerate(workflow_tasks) if t.status != TaskStatus.SUCCESS), None)
        if start_idx is None:
            raise BadRequestError("All tasks already succeeded")
        anchor_task = workflow_tasks[start_idx]
        retryable, reason = TaskService._can_retry_anchor_task(
            anchor_task,
            now=datetime.now(timezone.utc),
        )
        if not retryable:
            raise BadRequestError(reason)

        to_retry = workflow_tasks[start_idx:]
        signatures = []
        for t in to_retry:
            task_type_enum = TaskType.from_value(t.task_type)
            if not task_type_enum:
                raise BadRequestError(f"Unsupported task type {t.task_type} for retry")
            info: TaskTypeInfo = task_type_enum.value

            # Reset state for retry
            t.status = TaskStatus.PENDING
            t.retry_count = 0
            t.started_at = None
            t.completed_at = None
            t.error_message = None
            t.output_data = None
            t.worker_id = None
            t.execution_time_ms = None
            t.celery_task_id = None

            module_path, func_name = info.celery_task.rsplit(".", 1)
            module = import_module(module_path)
            celery_task = getattr(module, func_name)

            task_kwargs = {"task_id": t.id}
            task_kwargs.update(t.input_data or {})

            # Use immutable signature so prior task result isn't injected into args
            sig = celery_task.si(**task_kwargs)
            if info.max_retries is not None:
                sig.set(max_retries=info.max_retries)
            if info.timeout_seconds is not None:
                sig.set(time_limit=info.timeout_seconds)
            signatures.append(sig)

        await db.flush()
        await db.commit()

        # Submit chain and backfill celery ids
        if not signatures:
            raise BadRequestError("No tasks to retry")

        if len(signatures) == 1:
            result = signatures[0].apply_async()
            to_retry[0].celery_task_id = getattr(result, "id", None)
        else:
            chain_result = chain(*signatures).apply_async()
            current_result = chain_result
            for task in reversed(to_retry):
                task.celery_task_id = getattr(current_result, "id", None)
                current_result = getattr(current_result, "parent", None)

        await db.commit()

        return TaskRetryResponse(
            message="Task retry submitted",
            task_id=task_id,
            status="PENDING",
            retried_task_ids=[t.id for t in to_retry],
        )

    @staticmethod
    async def batch_retry_tasks(db: AsyncSession, task_ids: Iterable[str]) -> BatchRetryResponse:
        results: list[BatchRetryResult] = []
        success = 0
        failed = 0

        for tid in task_ids:
            try:
                retry_resp = await TaskService.retry_task(db, tid)
                results.append(
                    BatchRetryResult(
                        original_task_id=tid,
                        new_task_id=(retry_resp.retried_task_ids[0] if retry_resp.retried_task_ids else None),
                        status="success",
                    )
                )
                success += 1
            except JobPilotException as exc:
                results.append(
                    BatchRetryResult(
                        original_task_id=tid,
                        new_task_id=None,
                        status="failed",
                        error=exc.message,
                    )
                )
                failed += 1

        return BatchRetryResponse(
            message="Batch retry completed",
            success_count=success,
            failed_count=failed,
            results=results,
        )

    @staticmethod
    async def get_task_statistics(
        db: AsyncSession,
        *,
        status_filter: Optional[list[str]] = None,
        task_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> TaskStatisticsResponse:
        """Aggregate stats by task type."""
        filters = []
        if status_filter:
            filters.append(TaskExecution.status.in_(status_filter))
        if task_type:
            filters.append(TaskExecution.task_type == task_type)
        if start_time:
            filters.append(TaskExecution.created_at >= start_time)
        if end_time:
            filters.append(TaskExecution.created_at <= end_time)

        base = select(
            TaskExecution.task_type.label("task_type"),
            func.count().label("total"),
            func.avg(TaskExecution.execution_time_ms).label("avg_duration"),
            func.sum(
                case((TaskExecution.status == TaskStatus.FAILED, 1), else_=0)
            ).label("failed_count"),
        )
        if filters:
            base = base.where(and_(*filters))
        base = base.group_by(TaskExecution.task_type)

        stats_rows = (await db.execute(base)).all()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_filter = [TaskExecution.created_at >= today_start]
        if task_type:
            today_filter.append(TaskExecution.task_type == task_type)
        today_failed = await db.execute(
            select(
                TaskExecution.task_type,
                func.sum(case((TaskExecution.status == TaskStatus.FAILED, 1), else_=0)).label("failed"),
                func.count().label("total"),
            )
            .where(and_(*today_filter))
            .group_by(TaskExecution.task_type)
        )
        today_map = {row[0]: (row[1], row[2]) for row in today_failed.all()}

        cost_stmt = select(
            TaskExecution.task_type,
            func.coalesce(func.sum(AICall.estimated_cost), 0).label("cost"),
        ).join(AICall, TaskExecution.id == AICall.task_id)
        cost_stmt = cost_stmt.where(TaskExecution.created_at >= today_start)
        if task_type:
            cost_stmt = cost_stmt.where(TaskExecution.task_type == task_type)
        cost_stmt = cost_stmt.group_by(TaskExecution.task_type)
        cost_rows = (await db.execute(cost_stmt)).all()
        cost_map = {row[0]: float(row[1] or 0) for row in cost_rows}

        items = []
        for row in stats_rows:
            task_type_key = row.task_type or "unknown"
            total_count = row.total or 0
            failed_count = row.failed_count or 0
            failure_rate = (failed_count / total_count * 100) if total_count else 0.0

            today_failed_count, today_total_count = today_map.get(task_type_key, (0, 0)) if today_map else (0, 0)
            today_failure_rate = (today_failed_count / today_total_count * 100) if today_total_count else 0.0

            trend = "stable"
            if today_failure_rate > failure_rate + 2:
                trend = "up"
            elif today_failure_rate < failure_rate - 2:
                trend = "down"

            items.append(
                TaskTypeStats(
                    task_type=task_type_key,
                    avg_duration_ms=row.avg_duration,
                    failure_rate_pct=failure_rate,
                    today_failure_rate_pct=today_failure_rate,
                    trend=trend,
                    daily_cost=cost_map.get(task_type_key, 0.0),
                    total_count=total_count,
                )
            )

        return TaskStatisticsResponse(task_type_stats=items)
