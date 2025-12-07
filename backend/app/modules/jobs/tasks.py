"""Celery tasks for job analysis."""
import asyncio
from uuid import uuid4

from celery import Task

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import get_db
from app.core.llm.gateway import AgentGateway
from app.modules.jobs.models import SeekJob
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository
from agent_configs.schemas import AnalyzedJob


@celery_app.task(bind=True, max_retries=3)
def analyze_job_async(self: Task, job_id: int) -> dict:
    """
    Analyze a job using job_analyzer agent.

    On success: Create JobAnalysis record in database
    On failure: Task status updated by Celery, no database record created

    Args:
        self: Celery task instance
        job_id: ID of the job to analyze

    Returns:
        Dictionary with analysis_id and status
    """
    async def _run():
        async for db in get_db():
            # 1. Load job
            job = await JobRepository.get_by_id(db, job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # 2. Check if already analyzed
            existing = await JobAnalysisRepository.get_by_job_id(db, job_id)
            if existing:
                return {"analysis_id": existing.id, "status": "cached"}

            # 3. Prepare input content
            content = job.content or job.abstract or ""
            if not content:
                raise ValueError(f"Job {job_id} has no content to analyze")

            # 4. Call Agent Gateway
            ctx = {
                "db": db,
                "operation": "job_analysis",
                "job_id": job_id,
            }

            result = await AgentGateway.get().call(
                agent_id="job_analyzer",
                input_data=content,
                context=ctx,
            )

            # 5. Parse result
            if isinstance(result, AnalyzedJob):
                analysis_data = result.model_dump()
            else:
                analysis_data = result

            # 6. Save to database
            # Use version from Schema instead of config
            analysis_version = AnalyzedJob.__version__

            analysis = await JobAnalysisRepository.create(
                db=db,
                job_id=job_id,
                analysis_data=analysis_data,
                analysis_version=analysis_version,
            )

            await db.commit()

            return {
                "analysis_id": analysis.id,
                "status": "completed",
                "job_id": job_id,
            }

    return asyncio.run(_run())


@celery_app.task
def poll_unanalyzed_jobs() -> dict:
    """
    Periodic task: find jobs without analysis and trigger analysis.

    Schedule: Every 5 minutes via Celery Beat
    Batch size: Controlled by MAX_JOBS_PER_POLL config

    Returns:
        Dictionary with count of triggered tasks
    """
    async def _run():
        async for db in get_db():
            # Get unanalyzed jobs (limited by config)
            jobs = await JobRepository.get_unanalyzed_jobs(
                db,
                limit=settings.MAX_JOBS_PER_POLL
            )

            # Trigger analysis for each job
            triggered_count = 0
            for job in jobs:
                analyze_job_async.delay(job.id)
                triggered_count += 1

            return {
                "triggered": triggered_count,
                "total_found": len(jobs),
            }

    return asyncio.run(_run())
