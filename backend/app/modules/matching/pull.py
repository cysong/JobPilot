"""Celery task to enqueue matching for newly analyzed jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.workflow.models import TaskExecution
from app.modules.workflow.service import TaskService
from app.shared.enums import TaskType
from app.modules.workflow import AsyncBaseTask


@celery_app.task(base=AsyncBaseTask, bind=True)
async def pull_unmatched_jobs(self) -> dict:
    """Every 5 minutes: find new job analyses since last run and enqueue matching."""
    last_exec = await _get_last_execution_time(self.db)
    since = last_exec or datetime.now(timezone.utc) - timedelta(days=30)

    new_analyses = await JobAnalysisRepository.get_updated_since(self.db, since=since)
    if not new_analyses:
        return {"status": "no_new_job_analysis"}

    dispatched_ids = []
    for analysis in new_analyses:
        workflow_id = str(uuid4())
        await TaskService.submit_task(
            db=self.db,
            task_type=TaskType.JOB_USER_MATCHING,
            entity_type="job",
            entity_id=str(analysis.job_id),
            user_id=None,
            workflow_id=workflow_id,
            input_data={"job_analysis_id": analysis.id},
            job_analysis_id=analysis.id,
        )
        dispatched_ids.append(analysis.id)
    await self.db.commit()
    return {"status": "dispatched", "job_analysis_ids": dispatched_ids}


async def _get_last_execution_time(db: AsyncSession):
    stmt = (
        select(func.max(TaskExecution.created_at))
        .where(TaskExecution.task_type == "job_user_matching")
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
