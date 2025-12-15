"""Celery tasks for application workflows and outbox consumption."""
from __future__ import annotations

import logging

from app.core.celery_app import celery_app
from app.modules.applications.config import app_module_settings
from app.modules.workflow import AsyncBaseTask, DBTrackingTask

logger = logging.getLogger(__name__)


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


@celery_app.task(base=AsyncBaseTask)
async def run_outbox_consumer(self):
    """
    Periodic task to drain application outbox events.

    Processes events concurrently with controlled concurrency (max 5 by default).
    Each event gets its own database session to avoid race conditions.
    """
    from app.modules.applications.outbox_consumer import process_outbox_batch

    batch_size = app_module_settings.OUTBOX_BATCH_SIZE
    await process_outbox_batch(self.db, batch_size=batch_size)


@celery_app.task(bind=True, base=DBTrackingTask)
async def generate_cover_letter_task(self, application_id: str, workflow_id: str, task_id: str):
    """Entry point for cover letter generation Celery task."""
    await _execute_cover_letter_task(
        application_id=application_id,
        workflow_id=workflow_id,
        task_id=task_id,
        celery_task_id=self.request.id,
        db=self.db,
    )


async def _execute_cover_letter_task(
    *,
    db,
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
