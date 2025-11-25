"""Repository helpers for workflow executions."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import WorkflowExecution
from app.shared.enums import WorkflowStatus


class WorkflowRepository:
    """Data access helpers for workflow_executions."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        workflow_type: str,
        config_version: str,
        user_id: int,
        entity_id: str | None,
        input_data: dict,
    ) -> WorkflowExecution:
        workflow = WorkflowExecution(
            workflow_type=workflow_type,
            config_version=config_version,
            user_id=user_id,
            entity_id=entity_id,
            status=WorkflowStatus.PENDING,
            input_data=input_data,
        )
        db.add(workflow)
        await db.flush()
        return workflow

    @staticmethod
    async def get_by_id(db: AsyncSession, workflow_id: str) -> WorkflowExecution | None:
        return await db.get(WorkflowExecution, workflow_id)

    @staticmethod
    async def mark_running(
        db: AsyncSession,
        workflow: WorkflowExecution,
        *,
        celery_task_id: Optional[str] = None,
    ) -> None:
        workflow.status = WorkflowStatus.RUNNING
        workflow.celery_task_id = celery_task_id
        await db.flush()

    @staticmethod
    async def mark_completed(
        db: AsyncSession,
        workflow: WorkflowExecution,
        *,
        output_data: Optional[dict] = None,
    ) -> None:
        workflow.status = WorkflowStatus.COMPLETED
        workflow.output_data = output_data
        workflow.completed_at = datetime.utcnow()
        await db.flush()

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        workflow: WorkflowExecution,
        *,
        error_message: str,
    ) -> None:
        workflow.status = WorkflowStatus.FAILED
        workflow.error_message = error_message
        workflow.completed_at = datetime.utcnow()
        await db.flush()

    @staticmethod
    async def get_latest_by_entity(
        db: AsyncSession,
        *,
        workflow_type: str,
        entity_id: str,
    ) -> WorkflowExecution | None:
        query = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == workflow_type,
                WorkflowExecution.entity_id == entity_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def reset_for_retry(db: AsyncSession, workflow: WorkflowExecution) -> None:
        workflow.status = WorkflowStatus.PENDING
        workflow.error_message = None
        workflow.output_data = None
        workflow.celery_task_id = None
        workflow.completed_at = None
        await db.flush()
