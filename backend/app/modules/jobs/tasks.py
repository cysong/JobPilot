"""Celery tasks for job analysis."""
from uuid import uuid4

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.llm.gateway import AgentGateway
from app.modules.jobs.models import SeekJob
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository
from app.modules.workflow import DBTrackingTask, AsyncBaseTask, TaskService
from app.shared.enums import TaskType
from agent_configs.schemas import AnalyzedJob, TranslatedText


@celery_app.task(base=DBTrackingTask, bind=True, max_retries=3)
async def analyze_job_task(
    self,
    job_id: int,
    workflow_id: str,
    task_id: str,
) -> dict:
    """Analyze a job using job_analyzer agent."""
    job = await JobRepository.get_by_id(self.db, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    content = job.content or job.abstract or ""
    if not content:
        raise ValueError(f"Job {job_id} has no content to analyze")

    # Translate to Chinese (source assumed en, target zh) with strict formatting preservation
    # Build YAML-formatted string as agent expects
    translation_input = f"""source_language: en
            target_language: zh
            content_format: auto
            keep_placeholders: true
            style_hint: formal
            content: |
            {content}
        """
    translated = await AgentGateway.get().call(
        agent_id="universal_translator",
        input_data=translation_input,
        context={"db": self.db, "operation": "job_translation", "job_id": job_id},
    )
    cn_content = (
        translated.content if isinstance(translated, TranslatedText) else translated.get("content")
    )

    result = await AgentGateway.get().call(
        agent_id="job_analyzer",
        input_data=content,
        context={"db": self.db, "operation": "job_analysis", "job_id": job_id},
    )

    analysis_data = result.model_dump() if isinstance(result, AnalyzedJob) else result
    analysis_data["cn_content"] = cn_content
    analysis = await JobAnalysisRepository.upsert(
        db=self.db,
        job_id=job_id,
        analysis_data=analysis_data,
        analysis_version=AnalyzedJob.__version__,
    )
    await self.db.commit()

    return {"output_data": {"analysis_id": analysis.id, "status": "completed", "job_id": job_id}}


@celery_app.task(base=AsyncBaseTask, bind=True)
async def poll_unanalyzed_jobs(self) -> dict:
    """
    Periodic task: find jobs needing analysis and create tasks.
    Priority: re-analysis first, then missing analyses.
    """
    total_created = 0
    reanalysis_created = 0

    reanalysis_records = await JobAnalysisRepository.get_pending_reanalysis(
        self.db,
        limit=settings.MAX_JOBS_PER_POLL,
    )

    for analysis in reanalysis_records:
        await TaskService.submit_task(
            db=self.db,
            task_type=TaskType.JOB_ANALYSIS,
            entity_type="job",
            entity_id=str(analysis.job_id),
            user_id=1,
            input_data={"job_id": analysis.job_id},
            workflow_id=str(uuid4()),
        )
        reanalysis_created += 1

    total_created += reanalysis_created

    remaining = settings.MAX_JOBS_PER_POLL - reanalysis_created
    if remaining > 0:
        jobs = await JobRepository.get_jobs_without_analysis_task(
            self.db,
            limit=remaining,
        )
        for job in jobs:
            workflow_id = str(uuid4())
            await TaskService.submit_task(
                db=self.db,
                task_type=TaskType.JOB_ANALYSIS,
                entity_type="job",
                entity_id=str(job.id),
                user_id=1,
                input_data={"job_id": job.id},
                workflow_id=workflow_id,
            )
            total_created += 1

    return {
        "tasks_created": total_created,
        "reanalysis_count": reanalysis_created,
        "new_analysis_count": total_created - reanalysis_created,
    }
