"""Celery task to enqueue matching for newly analyzed jobs."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from celery import Task
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import get_db
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.matching.tasks import calculate_job_user_matches_task
from app.modules.workflow.models import TaskExecution, WorkflowExecution
from app.modules.workflow.service import WorkflowService
from app.shared.enums import TaskType, WorkflowType


@celery_app.task(name="matching.pull_unmatched_jobs", bind=True)
def pull_unmatched_jobs(self: Task) -> dict:
    """Every 5 minutes: find new job analyses since last run and enqueue matching."""

    async def _run():
        async for db in get_db():
            return await _execute(db)

    return _run_sync(_run())


async def _execute(db: AsyncSession) -> dict:
    last_exec = await _get_last_execution_time(db)
    since = last_exec or datetime.now(timezone.utc) - timedelta(days=30)

    new_analyses = await JobAnalysisRepository.get_updated_since(db, since=since)
    if not new_analyses:
        return {"status": "no_new_job_analysis"}

    # Create per-job workflows and tasks
    dispatched_ids = []
    for analysis in new_analyses:
        workflow = await WorkflowService.create_workflow(
            db=db,
            workflow_type=WorkflowType.JOB_ANALYSIS,
            user_id=None,  # system user
            entity_id=str(analysis.job_id),
            input_data={"job_id": analysis.job_id},
        )
        await WorkflowService.submit_task(
            db=db,
            workflow_id=workflow.id,
            task_type=TaskType.JOB_USER_MATCHES,
            input_data={"job_analysis_id": analysis.id},
            job_analysis_id=analysis.id,
        )
        dispatched_ids.append(analysis.id)
    await db.commit()
    return {"status": "dispatched", "job_analysis_ids": dispatched_ids}


async def _get_last_execution_time(db: AsyncSession):
    stmt = (
        select(func.max(TaskExecution.created_at))
        .where(TaskExecution.task_type == "job_user_matches")
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
