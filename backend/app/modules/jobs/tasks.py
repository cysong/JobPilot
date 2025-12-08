"""Celery tasks for job analysis."""
import asyncio
from uuid import uuid4

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import get_db
from app.core.llm.gateway import AgentGateway
from app.modules.jobs.models import SeekJob
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository
from app.modules.workflow.service import WorkflowService
from app.shared.enums import WorkflowType, TaskType
from agent_configs.schemas import AnalyzedJob


@celery_app.task(bind=True, max_retries=3)
def analyze_job_async(
    self: Task,
    job_id: int,
    workflow_id: str,
    task_id: str,
) -> dict:
    """
    Analyze a job using job_analyzer agent.

    Status management handled by task_status_guard decorator in _execute_job_analysis.

    Args:
        self: Celery task instance
        job_id: ID of the job to analyze
        workflow_id: Workflow ID (from WorkflowService)
        task_id: Task ID (from WorkflowService)

    Returns:
        Dictionary with analysis_id and status
    """
    async def _run():
        async for db in get_db():
            return await _execute_job_analysis(
                db=db,
                job_id=job_id,
                workflow_id=workflow_id,
                task_id=task_id,
            )

    return _run_sync(_run())


# Use task_status_guard from workflow module
from app.modules.workflow import task_status_guard


@task_status_guard(first=True, last=True)
async def _execute_job_analysis(
    *,
    db: AsyncSession,
    job_id: int,
    workflow_id: str,
    task_id: str,
) -> dict:
    """
    Execute job analysis business logic.

    Decorator (task_status_guard) automatically:
    - Marks workflow/task as RUNNING
    - Marks workflow/task as SUCCESS/FAILED
    - Records execution time
    - Handles errors

    This function only contains pure business logic.
    Supports both new analysis and re-analysis (upsert mode).
    """
    # 1. Load job
    job = await JobRepository.get_by_id(db, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    # 2. Prepare input content
    content = job.content or job.abstract or ""
    if not content:
        raise ValueError(f"Job {job_id} has no content to analyze")

    # 3. Call AI Agent
    result = await AgentGateway.get().call(
        agent_id="job_analyzer",
        input_data=content,
        context={"db": db, "operation": "job_analysis", "job_id": job_id},
    )

    # 4. Parse result
    if isinstance(result, AnalyzedJob):
        analysis_data = result.model_dump()
    else:
        analysis_data = result

    # 5. Upsert (create or update, and clear needs_reanalysis flag)
    analysis = await JobAnalysisRepository.upsert(
        db=db,
        job_id=job_id,
        analysis_data=analysis_data,
        analysis_version=AnalyzedJob.__version__,
    )
    await db.commit()

    return {
        "task_output_data": {
            "analysis_id": analysis.id,
            "status": "completed",
            "job_id": job_id,
        },
        "workflow_output_data": {
            "analysis_id": analysis.id,
        },
    }


@celery_app.task
def poll_unanalyzed_jobs() -> dict:
    """
    Periodic task: find jobs needing analysis and create workflows.

    Priority:
    1. Jobs marked for re-analysis (needs_reanalysis=True)
    2. Jobs without analysis workflow

    Schedule: Every 5 minutes via Celery Beat
    Batch size: Controlled by MAX_JOBS_PER_POLL config

    Returns:
        Dictionary with count of created workflows
    """
    async def _run():
        async for db in get_db():
            total_created = 0
            reanalysis_created = 0

            # 1. Priority: Process jobs marked for re-analysis
            reanalysis_records = await JobAnalysisRepository.get_pending_reanalysis(
                db,
                limit=settings.MAX_JOBS_PER_POLL
            )

            for analysis in reanalysis_records:
                # Create workflow for re-analysis
                workflow = await WorkflowService.create_workflow(
                    db=db,
                    workflow_type=WorkflowType.JOB_ANALYSIS,
                    user_id=1,  # System user ID - TODO: make configurable
                    entity_id=str(analysis.job_id),
                    input_data={"job_id": analysis.job_id},
                )

                # Create and submit task
                await WorkflowService.submit_task(
                    db=db,
                    workflow_id=workflow.id,
                    task_type=TaskType.JOB_ANALYSIS,
                    input_data={"job_id": analysis.job_id},
                    # Celery task arguments
                    job_id=analysis.job_id,
                )
                reanalysis_created += 1

            total_created += reanalysis_created

            # 2. If quota remaining, process new jobs without analysis
            remaining = settings.MAX_JOBS_PER_POLL - reanalysis_created
            if remaining > 0:
                jobs = await JobRepository.get_jobs_without_analysis_task(
                    db,
                    limit=remaining
                )

                for job in jobs:
                    # Create workflow
                    workflow = await WorkflowService.create_workflow(
                        db=db,
                        workflow_type=WorkflowType.JOB_ANALYSIS,
                        user_id=1,
                        entity_id=str(job.id),
                        input_data={"job_id": job.id},
                    )

                    # Create and submit task
                    await WorkflowService.submit_task(
                        db=db,
                        workflow_id=workflow.id,
                        task_type=TaskType.JOB_ANALYSIS,
                        input_data={"job_id": job.id},
                        # Celery task arguments
                        job_id=job.id,
                    )
                    total_created += 1

            return {
                "workflows_created": total_created,
                "reanalysis_count": reanalysis_created,
                "new_analysis_count": total_created - reanalysis_created,
            }

    return _run_sync(_run())


def _run_sync(coro):
    """
    Run an async coroutine inside Celery worker without closing the loop.

    asyncio.run() closes the loop after each call, which can break asyncpg
    connection cleanup between tasks. We reuse or recreate a loop and keep
    it alive for subsequent invocations.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
