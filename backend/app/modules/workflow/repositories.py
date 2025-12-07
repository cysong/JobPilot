"""Repository helpers for workflow and task executions."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.models import WorkflowExecution, TaskExecution
from app.shared.enums import WorkflowStatus, TaskStatus


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
        workflow_type: str | None = None,
        entity_id: str,
    ) -> WorkflowExecution | None:
        query = select(WorkflowExecution).where(
            WorkflowExecution.entity_id == entity_id,
        )
        if workflow_type:
            query = query.where(WorkflowExecution.workflow_type == workflow_type)

        query = query.order_by(WorkflowExecution.created_at.desc()).limit(1)
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


class TaskRepository:
    """Data access helpers for task_executions."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        workflow_id: str,
        task_name: str,
        task_type: str | None,
        priority: str = "normal",
        input_data: Optional[dict] = None,
    ) -> TaskExecution:
        task = TaskExecution(
            workflow_id=workflow_id,
            task_name=task_name,
            task_type=task_type,
            priority=priority,
            status=TaskStatus.PENDING,
            input_data=input_data,
        )
        db.add(task)
        await db.flush()
        return task

    @staticmethod
    async def get_by_id(db: AsyncSession, task_id: str) -> TaskExecution | None:
        return await db.get(TaskExecution, task_id)

    @staticmethod
    async def get_latest_by_workflow_and_name(
        db: AsyncSession,
        *,
        workflow_id: str,
        task_name: str,
    ) -> TaskExecution | None:
        query = (
            select(TaskExecution)
            .where(
                TaskExecution.workflow_id == workflow_id,
                TaskExecution.task_name == task_name,
            )
            .order_by(TaskExecution.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def reset_for_retry(db: AsyncSession, task: TaskExecution) -> None:
        task.status = TaskStatus.PENDING
        task.error_message = None
        task.output_data = None
        task.celery_task_id = None
        task.worker_id = None
        task.started_at = None
        task.completed_at = None
        task.execution_time_ms = None
        await db.flush()

    @staticmethod
    async def mark_running(
        db: AsyncSession,
        task: TaskExecution,
        *,
        celery_task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.celery_task_id = celery_task_id
        task.worker_id = worker_id or celery_task_id
        await db.flush()

    @staticmethod
    async def mark_success(
        db: AsyncSession,
        task: TaskExecution,
        *,
        output_data: Optional[dict] = None,
        execution_time_ms: Optional[int] = None,
    ) -> None:
        task.status = TaskStatus.SUCCESS
        task.output_data = output_data
        task.completed_at = datetime.utcnow()
        task.execution_time_ms = execution_time_ms
        await db.flush()

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        task: TaskExecution,
        *,
        error_message: str,
    ) -> None:
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.completed_at = datetime.utcnow()
        await db.flush()
