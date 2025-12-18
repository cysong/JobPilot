"""Celery tasks for application workflows and outbox consumption."""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.modules.applications.config import app_module_settings
from app.modules.workflow import AsyncBaseTask, DBTrackingTask
from app.modules.workflow.service import TaskService, TaskSubmissionSpec
from app.shared.enums import TaskType
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.resumes.repository import ResumeRepository

logger = logging.getLogger(__name__)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Register periodic tasks for outbox consumption."""
    interval = app_module_settings.OUTBOX_CONSUMER_INTERVAL_SECONDS
    sender.add_periodic_task(
        interval,
        run_outbox_consumer.s(),
        name=f"applications.outbox-consumer-{interval}s"
    )


@celery_app.task(base=AsyncBaseTask)
async def run_outbox_consumer(self):
    """Periodic task to drain application outbox events."""
    from app.modules.applications.outbox_consumer import process_outbox_batch
    batch_size = app_module_settings.OUTBOX_BATCH_SIZE
    await process_outbox_batch(self.db, batch_size=batch_size)


async def update_tailoring_progress(
    db: AsyncSession,
    application_id: str,
    step_name: str,
    message: str,
    status: str = "in_progress"
) -> None:
    """
    Update tailoring progress JSON in application table.
    
    Args:
        db: Database session
        application_id: Application ID
        step_name: Current step/task name (e.g., job_analysis, resume_tailoring)
        message: Human-readable status message
        status: status code (in_progress, completed, failed, skipped)
    """
    app = await ApplicationRepository.get_by_id(db, application_id)
    if not app:
        logger.warning(f"Application {application_id} not found for progress update")
        return

    progress = dict(app.tailoring_progress or {})
    
    # Initialize structure if empty
    if "steps" not in progress:
        progress["steps"] = {}
    
    # Update current step status
    progress["current_step"] = step_name
    progress["message"] = message
    progress["last_update"] = datetime.utcnow().isoformat()
    progress["steps"][step_name] = status

    # Explicitly mark modified for JSON field updates to ensure persistence
    app.tailoring_progress = progress
    
    logger.info(f"Progress [{application_id}]: {step_name} - {message} ({status})")
    # Note: We assume the caller or the task framework commits the transaction,
    # but for intermediate updates in a long task, we might want to commit here.
    # For now, we rely on the task's final commit or explicit flushes if needed.
    # Since this is often called inside a task that commits at the end, 
    # we might strictly need to commit if we want real-time updates visibility 
    # before the task finishes.
    await db.commit()


@celery_app.task(bind=True, base=DBTrackingTask)
async def application_initialization_task(
    self,
    application_id: str,
    job_id: int,
    resume_id: str,
    tailoring_level: str,
    workflow_id: str,
    task_id: str,
    is_retry: bool = False
):
    """
    Orchestrator task: Builds the sequential task chain for application generation.
    Checks existence of JobAnalysis and ResumeAnalysis to decide if they need to be run.

    Args:
        is_retry: Indicates if this is a retry attempt (affects logging and versioning)
    """
    db = self.db

    # Adjust logging and progress message based on retry status
    if is_retry:
        logger.info(f"Retrying application workflow for app_id={application_id}")
        progress_msg = "Retrying workflow from source resume..."
    else:
        logger.info(f"Initializing application workflow for app_id={application_id}")
        progress_msg = "Planning workflow steps..."

    await update_tailoring_progress(
        db, application_id, "initialization", progress_msg, "in_progress"
    )

    tasks_to_submit: list[TaskSubmissionSpec] = []
    
    # 1. Check Job Analysis
    job_analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
    # TODO: Check version mismatch if strictly required, similar to original logic
    if not job_analysis:
        logger.info(f"Job {job_id} analysis missing, adding analysis task.")
        tasks_to_submit.append(TaskSubmissionSpec(
            task_type=TaskType.JOB_ANALYSIS,
            input_data={"job_id": job_id},
        ))
    else:
        await update_tailoring_progress(
            db, application_id, "job_analysis", "Using cached job analysis", "skipped"
        )

    # 2. Check Resume Analysis
    # Note: resume_id here is the SOURCE resume ID.
    resume = await ResumeRepository.get_with_document(db, resume_id)
    if not resume:
        raise ValueError(f"Source resume {resume_id} not found")

    if not resume.analysis_result:
        logger.info(f"Resume {resume_id} analysis missing, adding analysis task.")
        tasks_to_submit.append(TaskSubmissionSpec(
            task_type=TaskType.RESUME_ANALYSIS,
            input_data={"resume_id": resume_id},
        ))
    else:
        await update_tailoring_progress(
            db, application_id, "resume_analysis", "Using cached resume analysis", "skipped"
        )

    # 3. Resume Tailoring (Always run)
    tasks_to_submit.append(TaskSubmissionSpec(
        task_type=TaskType.RESUME_TAILORING,
        input_data={
            "application_id": application_id,
            "resume_id": resume_id,
            "job_id": job_id,
            "tailoring_level": tailoring_level,
            "is_retry": is_retry
        }
    ))

    # 4. Cover Letter Generation (Always run)
    tasks_to_submit.append(TaskSubmissionSpec(
        task_type=TaskType.COVER_LETTER_GENERATION,
        input_data={
            "application_id": application_id,
            "job_id": job_id,
            "is_retry": is_retry
        }
    ))

    # Submit the chain
    from app.shared.enums import EntityType
    
    created_tasks = await TaskService.submit_sequential_tasks(
        db=db,
        entity_type=EntityType.APPLICATION.value,
        entity_id=application_id,
        user_id=resume.user_id,
        tasks=tasks_to_submit,
        workflow_id=workflow_id
    )
    
    task_ids = [t.id for t in created_tasks]
    await update_tailoring_progress(
        db, application_id, "initialization", f"Workflow planned: {len(created_tasks)} steps", "completed"
    )
    
    return {
        "output_data": {
            "workflow_id": workflow_id,
            "task_chain": task_ids,
            "tasks_count": len(created_tasks)
        }
    }


@celery_app.task(bind=True, base=DBTrackingTask)
async def resume_tailoring_task(
    self,
    application_id: str,
    resume_id: str,
    job_id: int,
    tailoring_level: str,
    workflow_id: str,
    task_id: str,
    is_retry: bool = False
):
    """
    Generate tailored resume content based on job and resume analysis.

    Always reads from source resume and creates a new versioned document.

    Args:
        resume_id: Source resume ID (not working document ID)
        is_retry: Indicates if this is a retry attempt (affects logging and versioning)
    """
    await update_tailoring_progress(
        self.db, application_id, "resume_tailoring", "Tailoring resume...", "in_progress"
    )

    from app.modules.applications.llm.resume_tailor import run_resume_tailoring

    result = await run_resume_tailoring(
        db=self.db,
        application_id=application_id,
        resume_id=resume_id,
        job_id=job_id,
        tailoring_level=tailoring_level,
        workflow_id=workflow_id,
        task_id=task_id,
        is_retry=is_retry
    )
    
    await update_tailoring_progress(
        self.db, application_id, "resume_tailoring", "Resume tailored successfully", "completed"
    )
    return result


@celery_app.task(bind=True, base=DBTrackingTask)
async def cover_letter_generation_task(
    self,
    application_id: str,
    workflow_id: str,
    task_id: str,
    job_id: int = None,
    is_retry: bool = False,
    **kwargs
):
    """
    Generate cover letter using tailored resume and job analysis.

    Always creates a new versioned document.

    Args:
        is_retry: Indicates if this is a retry attempt (affects logging and versioning)
    """
    await update_tailoring_progress(
        self.db, application_id, "cover_letter_generation", "Drafting cover letter...", "in_progress"
    )

    from app.modules.applications.llm.cover_letter_task import run_cover_letter_task
    from app.modules.applications.repositories.application_repo import ApplicationRepository

    application = await ApplicationRepository.get_with_dependencies(self.db, application_id)

    result = await run_cover_letter_task(
        db=self.db,
        application=application,
        workflow_id=workflow_id,
        task_id=task_id,
        is_retry=is_retry,
    )
    
    await update_tailoring_progress(
        self.db, application_id, "cover_letter_generation", "Cover letter generated", "completed"
    )
    
    return result
