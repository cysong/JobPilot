"""Celery tasks for application workflows and outbox consumption."""
from __future__ import annotations

import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.modules.applications.config import app_module_settings

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


async def _run_cover_letter_task(application_id: str, workflow_id: str, task_id: str, celery_task_id: str | None):
    """Async wrapper to run inside Celery task."""
    from app.modules.applications.llm.cover_letter_task import run_cover_letter_task

    async with async_session_factory() as db:
        await run_cover_letter_task(
            db=db,
            application_id=application_id,
            workflow_id=workflow_id,
            task_id=task_id,
            celery_task_id=celery_task_id,
        )
