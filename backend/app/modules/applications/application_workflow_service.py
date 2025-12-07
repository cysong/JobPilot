"""Application workflow orchestration service (decoupled from API)."""
from __future__ import annotations

import logging

from app.modules.applications.event_types import (
    ApplicationEventType,
    ApplicationCreatedPayload,
    ApplicationFailedPayload,
)
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository
from app.modules.applications.repositories.task_repo import TaskRepository
from app.modules.applications.repositories.workflow_repo import WorkflowRepository
from app.modules.applications.tasks import generate_cover_letter_task
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WorkflowService:
    """Encapsulates workflow/task creation and dispatch for applications."""

    WORKFLOW_TYPE = "application_generation"
    CONFIG_VERSION = "v1.0.0"

    @staticmethod
    async def init_workflow_for_application(
        db: AsyncSession,
        payload: ApplicationCreatedPayload,
    ):
        """Create workflow/task records and dispatch Celery task."""
        if payload.is_retry:
            workflow = await WorkflowRepository.get_latest_by_entity(
                db,
                workflow_type=WorkflowService.WORKFLOW_TYPE,
                entity_id=payload.application_id,
            )
            if workflow:
                await WorkflowRepository.reset_for_retry(db, workflow)
            else:
                workflow = await WorkflowRepository.create(
                    db,
                    workflow_type=WorkflowService.WORKFLOW_TYPE,
                    config_version=WorkflowService.CONFIG_VERSION,
                    user_id=payload.user_id,
                    entity_id=payload.application_id,
                    input_data={
                        "job_id": payload.job_id,
                        "resume_document_id": payload.resume_document_id,
                        "tailoring_level": payload.tailoring_level,
                    },
                )
        else:
            workflow = await WorkflowRepository.create(
                db,
                workflow_type=WorkflowService.WORKFLOW_TYPE,
                config_version=WorkflowService.CONFIG_VERSION,
                user_id=payload.user_id,
                entity_id=payload.application_id,
                input_data={
                    "job_id": payload.job_id,
                    "resume_document_id": payload.resume_document_id,
                    "tailoring_level": payload.tailoring_level,
                },
            )

        task = await TaskRepository.get_latest_by_workflow_and_name(
            db,
            workflow_id=workflow.id,
            task_name="generate_cover_letter",
        ) if payload.is_retry else None

        if payload.is_retry and task:
            await TaskRepository.reset_for_retry(db, task)
        else:
            task = await TaskRepository.create(
                db,
                workflow_id=workflow.id,
                task_name="generate_cover_letter",
                task_type="ai_agent",
                priority="normal",
                input_data={
                    "application_id": payload.application_id,
                    "job_id": payload.job_id,
                    "resume_document_id": payload.resume_document_id,
                },
            )

        await db.commit()

        try:
            generate_cover_letter_task.delay(
                application_id=payload.application_id,
                workflow_id=workflow.id,
                task_id=task.id,
            )
        except Exception as exc:  # noqa: BLE001
            # 仅记录调度异常，不修改任务/流程状态，也不写出 Outbox
            logger.error(
                "failed_to_dispatch_cover_letter_task",
                exc_info=exc,
                workflow_id=workflow.id,
                task_id=task.id,
                application_id=payload.application_id,
            )
            raise

        return workflow, task
