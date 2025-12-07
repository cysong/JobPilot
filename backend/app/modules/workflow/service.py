"""Universal workflow orchestration service for task management."""
from __future__ import annotations

import logging
from importlib import import_module
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.models import WorkflowExecution, TaskExecution
from app.modules.workflow.repositories import WorkflowRepository, TaskRepository
from app.shared.enums import WorkflowType, TaskType, TaskTypeInfo

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    Universal workflow orchestration service.

    Provides high-level API for creating and submitting tasks to Celery queue.
    Business modules should use this service for all task submissions.
    """

    # ============================================
    # Workflow Management
    # ============================================

    @staticmethod
    async def create_workflow(
        db: AsyncSession,
        *,
        workflow_type: WorkflowType,
        user_id: int,
        entity_id: str,
        input_data: Optional[dict] = None,
        config_version: str = "v1.0.0",
    ) -> WorkflowExecution:
        """
        Create a new workflow.

        Args:
            db: Database session
            workflow_type: Type of workflow
            user_id: User ID
            entity_id: Entity ID (e.g., job_id, application_id)
            input_data: Workflow input data
            config_version: Workflow config version

        Returns:
            Created WorkflowExecution instance
        """
        workflow = await WorkflowRepository.create(
            db=db,
            workflow_type=workflow_type.value,  # Convert enum to string
            config_version=config_version,
            user_id=user_id,
            entity_id=entity_id,
            input_data=input_data or {},
        )
        await db.flush()
        return workflow

    # ============================================
    # Task Creation and Submission
    # ============================================

    @staticmethod
    async def create_task(
        db: AsyncSession,
        *,
        workflow_id: str,
        task_type: str,
        task_name: str,
        input_data: Optional[dict] = None,
        depends_on: Optional[list[str]] = None,
    ) -> TaskExecution:
        """
        Create a new task within a workflow.

        Args:
            db: Database session
            workflow_id: Parent workflow ID
            task_type: Type of task (string value)
            task_name: Human-readable task name
            input_data: Task input data
            depends_on: List of task IDs this task depends on

        Returns:
            Created TaskExecution instance
        """
        task = await TaskRepository.create(
            db=db,
            workflow_id=workflow_id,
            task_type=task_type,
            task_name=task_name,
            input_data=input_data or {},
        )
        await db.flush()
        return task

    @staticmethod
    async def submit_task(
        db: AsyncSession,
        *,
        workflow_id: str,
        task_type: TaskType,
        input_data: Optional[dict] = None,
        **celery_task_kwargs,
    ) -> tuple[TaskExecution, Any]:
        """
        Create task record and submit to Celery queue with auto-configuration from enum.

        This is the recommended way to submit tasks from business modules.
        Task metadata (name, celery_task, max_retries, timeout) are automatically
        extracted from TaskType enum.

        Args:
            db: Database session
            workflow_id: Parent workflow ID
            task_type: Type of task (TaskType enum)
            input_data: Task input data (stored in DB)
            **celery_task_kwargs: Additional arguments for task execution (passed to Celery)

        Returns:
            Tuple of (TaskExecution, Celery AsyncResult)

        Example:
            # Job Analysis - all config from enum
            task, result = await WorkflowService.submit_task(
                db=db,
                workflow_id=workflow.id,
                task_type=TaskType.JOB_ANALYSIS,
                input_data={"job_id": 123},
                job_id=123,  # Passed to Celery task
            )

            # Cover Letter - override timeout
            task, result = await WorkflowService.submit_task(
                db=db,
                workflow_id=workflow.id,
                task_type=TaskType.COVER_LETTER_DRAFT,
                input_data={"application_id": "abc"},
                application_id="abc",
                time_limit=900,  # Override default 600s timeout
            )
        """
        # Extract metadata from TaskType enum
        info: TaskTypeInfo = task_type.value

        # 1. Create task record (store string value in DB)
        task = await WorkflowService.create_task(
            db=db,
            workflow_id=workflow_id,
            task_type=info.value,  # Store string: "job_analysis"
            task_name=info.display_name,  # Auto from enum: "Job Analysis"
            input_data=input_data,
        )
        await db.commit()

        # 2. Get Celery task function by path
        # e.g., "app.modules.jobs.tasks.analyze_job_async" -> actual function
        module_path, func_name = info.celery_task.rsplit(".", 1)
        module = import_module(module_path)
        celery_task = getattr(module, func_name)

        # 3. Build Celery options from enum (allow kwargs to override)
        celery_options = {}
        if info.max_retries is not None:
            celery_options["max_retries"] = info.max_retries
        if info.timeout_seconds is not None:
            celery_options["time_limit"] = info.timeout_seconds

        # Merge with user overrides
        celery_options.update(celery_task_kwargs)

        # 4. Submit to Celery queue
        # Always pass workflow_id and task_id to Celery task
        task_kwargs = {
            "workflow_id": workflow_id,
            "task_id": task.id,
        }
        task_kwargs.update(input_data or {})

        async_result = celery_task.apply_async(
            kwargs=task_kwargs,
            **celery_options,
        )

        # 5. Store Celery task ID
        task.celery_task_id = async_result.id
        await db.commit()

        logger.info(
            "task_submitted_to_celery",
            extra={
                "workflow_id": workflow_id,
                "task_id": task.id,
                "task_type": info.value,
                "celery_task_id": async_result.id,
            },
        )

        return task, async_result

    # ============================================
    # Helper Methods
    # ============================================

    @staticmethod
    async def get_workflow_by_entity(
        db: AsyncSession,
        entity_id: str,
        workflow_type: Optional[WorkflowType] = None,
    ) -> Optional[WorkflowExecution]:
        """
        Get workflow by entity.

        Useful for checking if a workflow already exists for an entity.

        Args:
            db: Database session
            entity_id: Entity ID
            workflow_type: Optional workflow type filter

        Returns:
            WorkflowExecution if found, None otherwise
        """
        return await WorkflowRepository.get_latest_by_entity(
            db,
            workflow_type=workflow_type.value if workflow_type else None,
            entity_id=entity_id,
        )
