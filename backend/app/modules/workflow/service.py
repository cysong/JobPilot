"""Task submission service (single-table task model)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Optional
from uuid import uuid4

from celery import chain
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.models import TaskExecution
from app.modules.workflow.repositories import TaskRepository
from app.shared.enums import TaskType, TaskTypeInfo

logger = logging.getLogger(__name__)


@dataclass
class TaskSubmissionSpec:
    """Spec for a single task in a sequential chain."""

    task_type: TaskType
    input_data: Optional[dict] = field(default_factory=dict)
    celery_kwargs: Optional[dict] = field(default_factory=dict)


class TaskService:
    """Create and submit tracked tasks to Celery."""

    @staticmethod
    async def submit_task(
        db: AsyncSession,
        *,
        task_type: TaskType,
        entity_type: str,
        entity_id: str,
        user_id: int | None = None,
        input_data: Optional[dict] = None,
        workflow_id: str | None = None,
        depends_on: Optional[list[str]] = None,
        **celery_kwargs: Any,
    ) -> TaskExecution:
        """
        Create a task_executions row and dispatch Celery task.

        If workflow_id is not provided, a single-task workflow uses task_id as workflow_id.
        """
        info: TaskTypeInfo = task_type.value
        task_id = str(uuid4())
        workflow_id = workflow_id or task_id

        task = await TaskRepository.create(
            db=db,
            id=task_id,
            workflow_id=workflow_id,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            task_type=info.value,
            task_name=info.display_name,
            input_data=input_data or {},
            depends_on=depends_on,
        )
        await db.flush()
        await db.commit()

        module_path, func_name = info.celery_task.rsplit(".", 1)
        module = import_module(module_path)
        celery_task = getattr(module, func_name)

        celery_options: dict[str, Any] = {}
        if info.max_retries is not None:
            celery_options["max_retries"] = info.max_retries
        if info.timeout_seconds is not None:
            celery_options["time_limit"] = info.timeout_seconds
        celery_options.update(celery_kwargs)

        task_kwargs = {
            "workflow_id": workflow_id,
            "task_id": task_id,
            **(input_data or {}),
        }

        async_result = celery_task.apply_async(kwargs=task_kwargs, **celery_options)
        task.celery_task_id = async_result.id
        await db.commit()

        logger.info(
            "task_submitted_to_celery",
            extra={
                "workflow_id": workflow_id,
                "task_id": task_id,
                "task_type": info.value,
                "celery_task_id": async_result.id,
            },
        )

        return task

    @staticmethod
    async def submit_sequential_tasks(
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        user_id: int | None,
        tasks: list[TaskSubmissionSpec],
        workflow_id: str | None = None,
    ) -> list[TaskExecution]:
        """
        Create tasks in order and dispatch via Celery chain to enforce sequencing.

        Args:
            db: AsyncSession
            entity_type: business entity type (job/resume/application)
            entity_id: business entity id
            user_id: optional user id
            tasks: ordered list of task specifications
            workflow_id: optional workflow id (defaults to first task id)
        """
        if not tasks:
            raise ValueError("tasks list cannot be empty")

        workflow_id = workflow_id or str(uuid4())
        created: list[TaskExecution] = []
        signatures = []
        prev_task_id: str | None = None

        for spec in tasks:
            info: TaskTypeInfo = spec.task_type.value
            task_id = str(uuid4())
            task = await TaskRepository.create(
                db=db,
                id=task_id,
                workflow_id=workflow_id,
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                task_type=info.value,
                task_name=info.display_name,
                input_data=spec.input_data or {},
                depends_on=[prev_task_id] if prev_task_id else None,
            )
            await db.flush()
            created.append(task)

            module_path, func_name = info.celery_task.rsplit(".", 1)
            module = import_module(module_path)
            celery_task = getattr(module, func_name)

            task_kwargs = {"workflow_id": workflow_id, "task_id": task_id}
            task_kwargs.update(spec.input_data or {})

            sig = celery_task.s(**task_kwargs)
            if info.max_retries is not None:
                sig.set(max_retries=info.max_retries)
            if info.timeout_seconds is not None:
                sig.set(time_limit=info.timeout_seconds)
            if spec.celery_kwargs:
                sig.set(**spec.celery_kwargs)

            signatures.append(sig)
            prev_task_id = task_id

        await db.commit()

        chain_result = chain(*signatures).apply_async()

        # Propagate Celery task IDs back to TaskExecution records (walk parents)
        current_result = chain_result
        for task in reversed(created):
            task.celery_task_id = getattr(current_result, "id", None)
            current_result = getattr(current_result, "parent", None)
        await db.commit()

        logger.info(
            "sequential_tasks_submitted",
            extra={
                "workflow_id": workflow_id,
                "task_ids": [t.id for t in created],
                "task_types": [t.task_type for t in created],
            },
        )

        return created


# Backward alias for callers still importing WorkflowService
WorkflowService = TaskService
