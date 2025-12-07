"""Decorators for workflow task status management."""
from __future__ import annotations

import functools
import logging
import time
from typing import Awaitable, Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.repositories import WorkflowRepository, TaskRepository

TaskFunc = Callable[..., Awaitable[Any]]

logger = logging.getLogger(__name__)


def task_status_guard(*, first: bool = False, last: bool = False) -> Callable[[TaskFunc], TaskFunc]:
    """
    Decorator to auto-manage task/workflow status.

    Args:
        first: Mark workflow as RUNNING when task starts (for first task in workflow)
        last: Mark workflow as COMPLETED when task succeeds (for last task in workflow)

    Usage:
        @task_status_guard(first=True, last=True)
        async def _execute_task(*, db: AsyncSession, workflow_id: str, task_id: str, ...) -> dict:
            # Business logic here
            return {
                "task_output_data": {...},
                "workflow_output_data": {...},
            }

    Automatic behavior:
        - Marks task as RUNNING at start
        - Marks workflow as RUNNING at start (if first=True)
        - On success:
            - Marks task as SUCCESS with output_data and execution_time_ms
            - Marks workflow as COMPLETED (if last=True)
        - On failure:
            - Marks task as FAILED with error_message
            - Marks workflow as FAILED with error_message
            - Re-raises exception for Celery retry handling
    """

    def decorator(func: TaskFunc) -> TaskFunc:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            db: AsyncSession = kwargs["db"]
            workflow_id: str = kwargs["workflow_id"]
            task_id: str = kwargs["task_id"]

            workflow = await WorkflowRepository.get_by_id(db, workflow_id)
            task = await TaskRepository.get_by_id(db, task_id)

            if not workflow or not task:
                logger.error(
                    "task_status_guard_missing_entities",
                    extra={"workflow_id": workflow_id, "task_id": task_id},
                )
                return

            start = time.perf_counter()

            # Mark task/workflow as running
            if first:
                await WorkflowRepository.mark_running(db, workflow)
            await TaskRepository.mark_running(db, task)
            await db.commit()

            try:
                # Execute business logic
                result = await func(*args, **kwargs)

                # Extract output data from result
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                task_output = {}
                workflow_output = {}
                if isinstance(result, dict):
                    task_output = result.get("task_output_data", {}) or {}
                    workflow_output = result.get(
                        "workflow_output_data", {}) or {}

                # Mark task as success
                await TaskRepository.mark_success(
                    db,
                    task,
                    output_data=task_output,
                    execution_time_ms=elapsed_ms,
                )

                # Mark workflow as completed if last task
                if last:
                    await WorkflowRepository.mark_completed(
                        db,
                        workflow,
                        output_data=workflow_output,
                    )
                await db.commit()
                return result
            except Exception as exc:  # noqa: BLE001
                # Mark task and workflow as failed, then re-raise for Celery retry
                await db.rollback()
                await TaskRepository.mark_failed(db, task, error_message=str(exc))
                await WorkflowRepository.mark_failed(db, workflow, error_message=str(exc))
                await db.commit()
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
