"""Repository helpers for workflow and task executions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.models import TaskExecution, AICall
from app.shared.enums import TaskStatus, AICallStatus


class TaskRepository:
    """Data access helpers for task_executions."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        id: str | None = None,
        workflow_id: str,
        entity_type: str,
        entity_id: str,
        user_id: int | None,
        task_name: str,
        task_type: str | None,
        priority: str = "normal",
        input_data: Optional[dict] = None,
        depends_on: Optional[list[str]] = None,
        step: int,
        total_steps: int,
    ) -> TaskExecution:
        task = TaskExecution(
            id=id,
            workflow_id=workflow_id,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            task_name=task_name,
            task_type=task_type,
            priority=priority,
            status=TaskStatus.PENDING,
            input_data=input_data,
            depends_on=depends_on or [],
            step=step,
            total_steps=total_steps,
        )
        db.add(task)
        await db.flush()
        return task

    @staticmethod
    async def get_by_id(db: AsyncSession, task_id: str) -> TaskExecution | None:
        return await db.get(TaskExecution, task_id)

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
        retry_count: Optional[int] = None,
    ) -> None:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        task.completed_at = None
        task.execution_time_ms = None
        task.error_message = None
        task.celery_task_id = celery_task_id
        task.worker_id = worker_id or celery_task_id
        if retry_count is not None:
            task.retry_count = retry_count
        await db.flush()

    @staticmethod
    async def mark_success(
        db: AsyncSession,
        task: TaskExecution,
        *,
        output_data: Optional[dict] = None,
        execution_time_ms: Optional[int] = None,
        retry_count: Optional[int] = None,
    ) -> None:
        task.status = TaskStatus.SUCCESS
        task.output_data = output_data
        task.error_message = None
        task.completed_at = datetime.now(timezone.utc)
        task.execution_time_ms = execution_time_ms
        if retry_count is not None:
            task.retry_count = retry_count
        await db.flush()

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        task: TaskExecution,
        *,
        error_message: str,
        retry_count: Optional[int] = None,
    ) -> None:
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.completed_at = datetime.now(timezone.utc)
        if retry_count is not None:
            task.retry_count = retry_count
        await db.flush()


class AICallRepository:
    """Data access helpers for AI calls."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        task_id: str,
        user_id: Optional[int],
        agent_id: str,
        agent_version: str,
        model: str,
        status: AICallStatus,
        latency_ms: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        requests: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        error_message: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> AICall:
        """
        Create a new AI call record.

        Args:
            db: Database session
            workflow_id: Associated workflow ID
            task_id: Associated task ID
            user_id: User who initiated the call
            agent_id: Agent identifier
            agent_version: Agent configuration version
            model: Model name (e.g., "gpt-4o")
            status: Call status (SUCCESS, ERROR, etc.)
            latency_ms: Call latency in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            total_tokens: Total tokens used
            requests: Number of API requests made
            estimated_cost: Estimated cost in USD
            error_message: Error message if failed
            meta: Additional metadata

        Returns:
            Created AICall instance
        """
        ai_call = AICall(
            task_id=task_id,
            user_id=user_id,
            model=model,
            agent_id=agent_id,
            agent_version=agent_version,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            requests=requests,
            estimated_cost=estimated_cost,
            error_message=error_message,
            meta=meta or {},
        )
        db.add(ai_call)
        await db.flush()
        return ai_call

    @staticmethod
    async def get_by_id(db: AsyncSession, ai_call_id: int) -> AICall | None:
        """Get AI call by ID."""
        query = select(AICall).where(AICall.id == ai_call_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_task_id(db: AsyncSession, task_id: str) -> list[AICall]:
        """Get all AI calls for a task."""
        query = select(AICall).where(AICall.task_id == task_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_user_id(
        db: AsyncSession, user_id: int, limit: int = 100
    ) -> list[AICall]:
        """Get recent AI calls for a user."""
        query = (
            select(AICall)
            .where(AICall.user_id == user_id)
            .order_by(AICall.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())
