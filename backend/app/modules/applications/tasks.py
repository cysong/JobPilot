"""Celery tasks for application workflows and outbox consumption."""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Awaitable, Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.modules.applications.config import app_module_settings
from app.modules.applications.models import WorkflowExecution, TaskExecution
from app.modules.applications.repositories.workflow_repo import WorkflowRepository
from app.modules.applications.repositories.task_repo import TaskRepository

TaskFunc = Callable[..., Awaitable[Any]]

logger = logging.getLogger(__name__)


def task_status_guard(*, first: bool = False, last: bool = False) -> Callable[[TaskFunc], TaskFunc]:
    """
    Decorator to auto-manage task/workflow status.

    - first: mark workflow running together with task running.
    - last: mark workflow completed when task succeeds.
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

            if first:
                await WorkflowRepository.mark_running(db, workflow)
            await TaskRepository.mark_running(db, task)
            await db.commit()

            try:
                result = await func(*args, **kwargs)

                elapsed_ms = int((time.perf_counter() - start) * 1000)
                task_output = {}
                workflow_output = {}
                if isinstance(result, dict):
                    task_output = result.get("task_output_data", {}) or {}
                    workflow_output = result.get(
                        "workflow_output_data", {}) or {}

                await TaskRepository.mark_success(
                    db,
                    task,
                    output_data=task_output,
                    execution_time_ms=elapsed_ms,
                )
                if last:
                    await WorkflowRepository.mark_completed(
                        db,
                        workflow,
                        output_data=workflow_output,
                    )
                await db.commit()
                return result
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                await TaskRepository.mark_failed(db, task, error_message=str(exc))
                await WorkflowRepository.mark_failed(db, workflow, error_message=str(exc))
                await db.commit()
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Register periodic tasks for outbox consumption."""
    interval = app_module_settings.OUTBOX_CONSUMER_INTERVAL_SECONDS
    sender.add_periodic_task(
        interval,
        run_outbox_consumer.s(),
        name=f"applications.outbox-consumer-{interval}s"
    )
    logger.info(f"Registered outbox consumer with {interval}s interval")


@celery_app.task(name="applications.run_outbox_consumer")
def run_outbox_consumer():
    """
    Periodic task to drain application outbox events.

    Processes events concurrently with controlled concurrency (max 5 by default).
    Each event gets its own database session to avoid race conditions.
    """
    from app.modules.applications.outbox_consumer import process_outbox_batch

    async def _run():
        async with async_session_factory() as db:
            batch_size = app_module_settings.OUTBOX_BATCH_SIZE
            await process_outbox_batch(db, batch_size=batch_size)

    asyncio.run(_run())


@celery_app.task(name="applications.generate_cover_letter", bind=True)
def generate_cover_letter_task(self, application_id: str, workflow_id: str, task_id: str):
    """Entry point for cover letter generation Celery task."""
    asyncio.run(
        _run_cover_letter_task(
            application_id=application_id,
            workflow_id=workflow_id,
            task_id=task_id,
            celery_task_id=self.request.id,
        )
    )


async def _run_cover_letter_task(
    application_id: str,
    workflow_id: str,
    task_id: str,
    celery_task_id: str | None,
):
    """Async bootstrap to create DB session and invoke the decorated handler."""
    async with async_session_factory() as db:

        await _execute_cover_letter_task(
            db=db,
            application_id=application_id,
            workflow_id=workflow_id,
            task_id=task_id,
            celery_task_id=celery_task_id,
        )


@task_status_guard(first=True, last=True)
async def _execute_cover_letter_task(
    *,
    db: AsyncSession,
    application_id: str,
    workflow_id: str,
    task_id: str,
    celery_task_id: str | None,
):
    """Async wrapper to run inside Celery task with status management."""
    from app.modules.applications.llm.cover_letter_task import run_cover_letter_task
    from app.modules.applications.repositories.application_repo import ApplicationRepository
    application = await ApplicationRepository.get_with_dependencies(db, application_id)

    await run_cover_letter_task(
        db=db,
        application=application,
        workflow_id=workflow_id,
        task_id=task_id,
        celery_task_id=celery_task_id,
    )
