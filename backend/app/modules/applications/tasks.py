"""Celery tasks for application workflows and outbox consumption."""
from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.core.database import async_session_factory


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Register periodic tasks for outbox consumption."""
    sender.add_periodic_task(5.0, run_outbox_consumer.s(), name="applications.outbox-consumer-5s")


@celery_app.task(name="applications.run_outbox_consumer")
def run_outbox_consumer():
    """Periodic task to drain application outbox events."""
    from app.modules.applications.outbox_consumer import process_outbox_batch

    async def _run():
        async with async_session_factory() as db:
            await process_outbox_batch(db, batch_size=100)

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
    from app.modules.applications.service import ApplicationService

    async with async_session_factory() as db:
        await ApplicationService.run_cover_letter_pipeline(
            db=db,
            application_id=application_id,
            workflow_id=workflow_id,
            task_id=task_id,
            celery_task_id=celery_task_id,
        )
