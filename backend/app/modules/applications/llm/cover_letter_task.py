"""Cover letter generation task logic using AgentGateway + YAML agents."""
from __future__ import annotations

import time
from typing import Optional, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas import AnalyzedJob, AnalyzedResume, CoverLetterDraft, ReviewResult
from app.core.llm.gateway import AgentGateway
from app.core.llm.types import GatewayContext
from app.modules.applications.event_types import (
    ApplicationEventType,
    ApplicationFailedPayload,
    ApplicationReadyPayload,
)
from app.modules.applications.models import (
    AICall,
    Application,
    TaskExecution,
    WorkflowExecution,
)
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository
from app.modules.applications.repositories.task_repo import TaskRepository
from app.modules.applications.repositories.workflow_repo import WorkflowRepository
from app.modules.jobs.models import SeekJob
from app.modules.resumes.models import Document, DocumentFormat
from app.modules.resumes.service import ResumeService
from app.shared.enums import AICallStatus


WORKFLOW_VERSION = "v1.0.0"
MAX_REVIEW_ITERATIONS = 2
REVIEW_PASS_SCORE = 8.0


async def run_cover_letter_task(
    db: AsyncSession,
    application_id: str,
    workflow_id: str,
    task_id: str,
    celery_task_id: Optional[str] = None,
):
    """Execute cover letter generation task via AgentGateway."""
    start_time = time.perf_counter()

    application = await ApplicationRepository.get_with_dependencies(db, application_id)
    workflow = await WorkflowRepository.get_by_id(db, workflow_id)
    task = await TaskRepository.get_by_id(db, task_id)

    if not application or not workflow or not task:
        return

    await WorkflowRepository.mark_running(
        db,
        workflow,
        celery_task_id=celery_task_id,
    )
    await TaskRepository.mark_running(
        db,
        task,
        celery_task_id=celery_task_id,
        worker_id=celery_task_id,
    )
    await ApplicationRepository.mark_tailoring(db, application)
    await db.commit()

    try:
        ctx: GatewayContext = {
            "db": db,
            "workflow_id": workflow.id,
            "task_id": task.id,
            "user_id": application.user_id,
            "operation": "cover_letter",
        }
        gateway = AgentGateway()

        job_analysis, _ = await _analyze_job(gateway, application.job, ctx)
        resume_analysis, _ = await _analyze_resume(gateway, application.resume_document, ctx)

        cover_letter_content, writer_usage, writer_latency_ms, review_result = await _generate_with_review(
            gateway=gateway,
            application=application,
            job_analysis=job_analysis,
            resume_analysis=resume_analysis,
            ctx=ctx,
        )

        cover_doc_id = str(uuid4())
        cover_document = Document(
            id=cover_doc_id,
            root_id=cover_doc_id,
            parent_id=None,
            format=DocumentFormat.MARKDOWN,
            content=cover_letter_content,
            content_hash=ResumeService._calculate_content_hash(cover_letter_content),
            change_comments="AI-generated cover letter",
            extra_metadata={"application_id": application.id},
            created_by=application.user_id,
        )
        db.add(cover_document)

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        await WorkflowRepository.mark_completed(
            db,
            workflow,
            output_data={
                "cover_letter_document_id": cover_doc_id,
                "review_result": review_result.model_dump() if review_result else None,
            },
        )
        await TaskRepository.mark_success(
            db,
            task,
            output_data={"cover_letter_document_id": cover_doc_id},
            execution_time_ms=execution_time_ms,
        )
        await ApplicationRepository.mark_ready(
            db,
            application,
            cover_letter_document_id=cover_doc_id,
        )

        # Record AI call for writer agent (gateway already emits Outbox ai_call_completed)
        ai_call = AICall(
            workflow_id=workflow.id,
            task_id=task.id,
            user_id=application.user_id,
            model="gpt-4o",
            prompt_id="cover_letter_writer",
            prompt_version=WORKFLOW_VERSION,
            latency_ms=writer_latency_ms,
            input_tokens=getattr(writer_usage, "input_tokens", None),
            output_tokens=getattr(writer_usage, "output_tokens", None),
            total_tokens=getattr(writer_usage, "total_tokens", None),
            status=AICallStatus.SUCCESS,
            meta={"application_id": application.id},
        )
        db.add(ai_call)

        await OutboxRepository.enqueue_event(
            db,
            event_type=ApplicationEventType.APPLICATION_READY.value,
            aggregate_type="application",
            aggregate_id=application.id,
            payload=ApplicationReadyPayload(
                application_id=application.id,
                cover_letter_document_id=cover_doc_id,
                status=application.status.value,
            ).model_dump(),
            meta={"user_id": application.user_id},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await _handle_failure(
            db=db,
            application=application,
            workflow=workflow,
            task=task,
            error=str(exc),
        )


async def _analyze_job(
    gateway: AgentGateway,
    job: SeekJob,
    ctx: GatewayContext,
) -> Tuple[AnalyzedJob, object]:
    """Run job_analyzer agent."""
    content = job.content or job.abstract or ""
    result, usage = await gateway.call(
        agent_id="job_analyzer",
        input_data=content,
        context={**ctx, "operation": "job_analysis"},
    )
    if isinstance(result, AnalyzedJob):
        return result, usage
    return AnalyzedJob(**result), usage


async def _analyze_resume(
    gateway: AgentGateway,
    resume_document: Document,
    ctx: GatewayContext,
) -> Tuple[AnalyzedResume, object]:
    """Run resume_analyzer agent."""
    result, usage = await gateway.call(
        agent_id="resume_analyzer",
        input_data=resume_document.content,
        context={**ctx, "operation": "resume_analysis"},
    )
    if isinstance(result, AnalyzedResume):
        return result, usage
    return AnalyzedResume(**result), usage


async def _generate_with_review(
    gateway: AgentGateway,
    application: Application,
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    ctx: GatewayContext,
) -> tuple[str, object, int, Optional[ReviewResult]]:
    """Generate draft, review, and iterate up to MAX_REVIEW_ITERATIONS."""
    feedback: str = ""
    last_review: Optional[ReviewResult] = None
    writer_usage = None
    writer_latency_ms = 0

    for attempt in range(MAX_REVIEW_ITERATIONS):
        writer_input = _build_writer_prompt(
            job_analysis=job_analysis,
            resume_analysis=resume_analysis,
            tailoring_level=application.tailoring_level,
            feedback=feedback,
        )
        writer_start = time.perf_counter()
        draft_output, writer_usage = await gateway.call(
            agent_id="cover_letter_writer",
            input_data=writer_input,
            context={**ctx, "operation": f"cover_letter_generate_attempt_{attempt+1}"},
        )
        writer_latency_ms = int((time.perf_counter() - writer_start) * 1000)
        draft = draft_output if isinstance(draft_output, CoverLetterDraft) else CoverLetterDraft(**draft_output)
        draft_text = _render_cover_letter(draft)

        review_input = _build_reviewer_input(
            draft_text=draft_text,
            job_analysis=job_analysis,
            tailoring_level=application.tailoring_level,
        )
        review_output, _ = await gateway.call(
            agent_id="reviewer",
            input_data=review_input,
            context={**ctx, "operation": f"cover_letter_review_attempt_{attempt+1}"},
        )
        last_review = review_output if isinstance(review_output, ReviewResult) else ReviewResult(**review_output)

        if (not last_review.needs_revision) and (last_review.overall_score >= REVIEW_PASS_SCORE):
            return draft_text, writer_usage, writer_latency_ms, last_review

        feedback = _build_feedback(last_review)

    # Return last attempt even if review not passing
    return draft_text, writer_usage, writer_latency_ms, last_review


def _render_cover_letter(draft: CoverLetterDraft) -> str:
    """Render CoverLetterDraft to markdown text."""
    body = "\n\n".join(draft.body_paragraphs or [])
    return f"{draft.opening}\n\n{body}\n\n{draft.closing}"


def _build_writer_prompt(
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    tailoring_level: str,
    feedback: str,
) -> str:
    """Compose input text for cover_letter_writer agent."""
    required_skills = ", ".join(job_analysis.required_skills or [])
    optional_skills = ", ".join(job_analysis.optional_skills or [])
    soft_skills = ", ".join(job_analysis.soft_skills or [])
    tech_skills = ", ".join(resume_analysis.technical_skills or [])
    resume_soft_skills = ", ".join(resume_analysis.soft_skills or [])
    achievements = "\n- ".join(resume_analysis.quantified_achievements or [])

    return (
        f"Tailoring level: {tailoring_level or 'light'}\n"
        f"Job required skills: {required_skills}\n"
        f"Job preferred skills: {optional_skills}\n"
        f"Job soft skills: {soft_skills}\n"
        f"Resume technical skills: {tech_skills}\n"
        f"Resume soft skills: {resume_soft_skills}\n"
        f"Resume achievements:\n- {achievements if achievements else 'N/A'}\n"
        f"Previous feedback:\n{feedback or 'N/A'}\n"
    )


def _build_reviewer_input(
    draft_text: str,
    job_analysis: AnalyzedJob,
    tailoring_level: str,
) -> str:
    """Compose input text for reviewer agent."""
    required_skills = ", ".join(job_analysis.required_skills or [])
    optional_skills = ", ".join(job_analysis.optional_skills or [])
    soft_skills = ", ".join(job_analysis.soft_skills or [])

    return (
        f"Tailoring level: {tailoring_level or 'light'}\n"
        f"Job required skills: {required_skills}\n"
        f"Job preferred skills: {optional_skills}\n"
        f"Job soft skills: {soft_skills}\n\n"
        f"Cover letter draft:\n{draft_text}"
    )


def _build_feedback(review: ReviewResult) -> str:
    """Summarize reviewer feedback for the next iteration."""
    issues = review.issues or []
    issues_text = "\n- ".join(issues)
    return (
        f"Overall score: {review.overall_score}\n"
        f"Needs revision: {review.needs_revision}\n"
        f"Issues:\n- {issues_text if issues_text else 'No issues provided'}"
    )


async def _handle_failure(
    db: AsyncSession,
    application: Application,
    workflow: WorkflowExecution,
    task: TaskExecution,
    error: str,
):
    """Mark workflow/task/application as failed and write outbox event."""
    await WorkflowRepository.mark_failed(db, workflow, error_message=error)
    await TaskRepository.mark_failed(db, task, error_message=error)
    await ApplicationRepository.mark_failed(db, application, error)

    await OutboxRepository.enqueue_event(
        db,
        event_type=ApplicationEventType.APPLICATION_FAILED.value,
        aggregate_type="application",
        aggregate_id=application.id,
        payload=ApplicationFailedPayload(
            application_id=application.id,
            error=error,
        ).model_dump(),
        meta={"user_id": application.user_id},
    )
    await db.commit()
