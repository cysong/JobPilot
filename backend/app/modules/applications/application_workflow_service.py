"""Application workflow helper for cover letter generation (single-table model)."""
from __future__ import annotations

import logging
from uuid import uuid4

from app.modules.applications.event_types import (
    ApplicationEventType,
    ApplicationCreatedPayload,
    ApplicationFailedPayload,
)
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository
from app.modules.workflow.service import TaskService
from app.shared.enums import TaskType
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ApplicationWorkflowHelper:
    """Helper for creating cover letter generation tasks."""

    WORKFLOW_TYPE = "application_generation"
    CONFIG_VERSION = "v1.0.0"

    @staticmethod
    async def init_workflow_for_application(
        db: AsyncSession,
        payload: ApplicationCreatedPayload,
    ):
        """Create task record and dispatch Celery task (single-table model)."""
        workflow_id = str(uuid4())
        task = await TaskService.submit_task(
            db=db,
            workflow_id=workflow_id,
            task_type=TaskType.COVER_LETTER_DRAFT,
            entity_type="application",
            entity_id=payload.application_id,
            user_id=payload.user_id,
            input_data={
                "application_id": payload.application_id,
                "job_id": payload.job_id,
                "resume_document_id": payload.resume_document_id,
                "tailoring_level": payload.tailoring_level,
                "is_retry": payload.is_retry,
            },
            application_id=payload.application_id,
            job_id=payload.job_id,
            resume_document_id=payload.resume_document_id,
            tailoring_level=payload.tailoring_level,
        )
        await db.commit()
        return workflow_id, task

    @staticmethod
    async def mark_application_failed(
        db: AsyncSession,
        payload: ApplicationFailedPayload,
    ) -> None:
        """Record application failure in outbox."""
        application = await ApplicationRepository.get_by_id(db, payload.application_id)
        if not application:
            logger.warning("application_not_found_on_failure", extra={"application_id": payload.application_id})
            return

        await OutboxRepository.add_event(
            db=db,
            event_type=ApplicationEventType.APPLICATION_FAILED,
            payload=payload.model_dump(),
        )
        await db.commit()
