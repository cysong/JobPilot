"""Celery tasks for job analysis."""
import logging
import time

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.llm.gateway import AgentGateway
from app.modules.jobs.repository import JobRepository, JobAnalysisRepository
from app.modules.workflow import DBTrackingTask, AsyncBaseTask, TaskService
from app.shared.enums import TaskType
from agent_configs.schemas import AnalyzedJob

logger = logging.getLogger(__name__)


def _extract_translated_content(translated: str) -> str:
    """Accept only the new plain-text translator output contract."""
    if isinstance(translated, str):
        return translated
    raise TypeError("universal_translator must return plain text output")


@celery_app.task(base=DBTrackingTask, bind=True)
async def analyze_job_task(
    self,
    job_id: int,
    task_id: str,
) -> dict:
    """Analyze a job using job_analyzer agent."""
    # Only `content` and `abstract` are needed; skip the full row + analysis
    # relationship that ``get_by_id`` would pull in.
    job = await JobRepository.get_content(self.db, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    content = job.content or job.abstract or ""
    if not content:
        raise ValueError(f"Job {job_id} has no content to analyze")

    # Translate to Chinese (source assumed en, target zh) with strict formatting preservation
    # Build YAML-formatted string as agent expects
    translation_input = f"""source_language: en
            target_language: zh-CN
            content_format: auto
            keep_placeholders: true
            style_hint: formal
            content: |
            {content}
        """
    translated = await AgentGateway.get().call(
        agent_id="universal_translator",
        input_data=translation_input,
        context={"db": self.db, "task_id": task_id},
    )
    cn_content = _extract_translated_content(translated)

    result = await AgentGateway.get().call(
        agent_id="job_analyzer",
        input_data=content,
        context={"db": self.db, "task_id": task_id},
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


@celery_app.task(base=AsyncBaseTask, bind=True, ignore_result=True)
async def poll_unanalyzed_jobs(self) -> dict:
    """
    Periodic task: find jobs needing analysis and create tasks.
    Priority: re-analysis first, then missing analyses.
    """
    start_time = time.perf_counter()
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
            entity_id=str(analysis.job_id),
            input_data={"job_id": analysis.job_id}
        )
        # Clear needs_reanalysis flag immediately after task submission
        # This prevents duplicate task creation in subsequent poll cycles
        analysis.needs_reanalysis = False
        reanalysis_created += 1

    # Commit the flag updates
    await self.db.commit()
    total_created += reanalysis_created

    remaining = settings.MAX_JOBS_PER_POLL - reanalysis_created
    if remaining > 0:
        jobs = await JobRepository.get_jobs_without_analysis_task(
            self.db,
            limit=remaining,
        )
        for job in jobs:
            await TaskService.submit_task(
                db=self.db,
                task_type=TaskType.JOB_ANALYSIS,
                entity_id=str(job.id),
                input_data={"job_id": job.id},
            )
            total_created += 1

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    new_analysis = total_created - reanalysis_created
    logger.info(f"poll_unanalyzed_jobs completed: reanalysis={reanalysis_created}, new={new_analysis}, total={total_created}, time={elapsed_ms}ms")

    return {
        "tasks_created": total_created,
        "reanalysis_count": reanalysis_created,
        "new_analysis_count": new_analysis,
    }
