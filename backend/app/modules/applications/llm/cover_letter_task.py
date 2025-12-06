"""Cover letter generation task logic using AgentGateway + YAML agents."""
from __future__ import annotations

from typing import Optional, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas import AnalyzedJob, AnalyzedResume, CoverLetterDraft, ReviewResult
from app.core.llm.gateway import AgentGateway
from app.core.llm.types import GatewayContext
from app.modules.applications.event_types import (
    ApplicationEventType,
    ApplicationReadyPayload,
)
from app.modules.applications.models import Application
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository
from app.modules.jobs.models import SeekJob
from app.modules.resumes.models import Document, DocumentFormat
from app.modules.resumes.service import ResumeService


WORKFLOW_VERSION = "v1.0.0"
MAX_REVIEW_ITERATIONS = 2
REVIEW_PASS_SCORE = 8.0


async def run_cover_letter_task(
    db: AsyncSession,
    application: Application,
    workflow_id: str,
    task_id: str
):
    """Execute cover letter generation task via AgentGateway."""
    ctx: GatewayContext = {
        "db": db,
        "workflow_id": workflow_id,
        "task_id": task_id,
        "user_id": application.user_id,
        "operation": "cover_letter",
    }

    job_analysis = await _get_job_analysis(application.job_id, db)
    resume_analysis = await _analyze_resume(application.resume_document, ctx)

    cover_letter_content, review_result = await _generate_with_review(
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
        content_hash=ResumeService._calculate_content_hash(
            cover_letter_content),
        change_comments="AI-generated cover letter",
        extra_metadata={"application_id": application.id},
        created_by=application.user_id,
    )
    db.add(cover_document)

    workflow_output_data = {
        "cover_letter_document_id": cover_doc_id,
        "review_result": review_result.model_dump() if review_result else None,
    }
    task_output_data = {"cover_letter_document_id": cover_doc_id}

    await ApplicationRepository.mark_ready(
        db,
        application,
        cover_letter_document_id=cover_doc_id,
    )

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

    return {
        "task_output_data": task_output_data,
        "workflow_output_data": workflow_output_data,
    }


async def _get_job_analysis(
    job_id: int,
    db: AsyncSession,
) -> AnalyzedJob:
    """
    Get cached job analysis or trigger async analysis.

    Strategy:
    1. Check job_analyses table
    2. If exists and version matches, return cached result
    3. If version outdated or missing, trigger analyze_job_async and raise Retry exception
    """
    from app.modules.jobs.repository import JobAnalysisRepository
    from app.modules.jobs.tasks import analyze_job_async
    from celery.exceptions import Retry

    # Try to get cached analysis
    cached = await JobAnalysisRepository.get_by_job_id(db, job_id)

    if cached:
        # Check if version is outdated
        current_version = AnalyzedJob.__version__
        if cached.analysis_version != current_version:
            # Version mismatch: delete old analysis and trigger re-analysis
            await JobAnalysisRepository.delete_by_job_id(db, job_id)
            await db.commit()

            analyze_job_async.delay(job_id)
            raise Retry(
                message=f"Job {job_id} analysis outdated (v{cached.analysis_version} -> v{current_version}), re-analyzing",
                countdown=30,
            )

        # Version matches: convert DB model to Pydantic schema
        return AnalyzedJob(
            required_skills=cached.required_skills or [],
            preferred_skills=cached.preferred_skills or [],
            certifications=cached.certifications or [],
            tech_stack=cached.tech_stack or [],
            seniority=cached.seniority,
            key_responsibilities=cached.key_responsibilities or [],
            experience_years=cached.experience_years,
            education_requirement=cached.education_requirement,
            soft_skills=cached.soft_skills or [],
            company_culture_keywords=cached.company_culture_keywords or [],
            hiring_priorities=cached.hiring_priorities or [],
        )

    # Cache miss: trigger analysis and retry this task
    analyze_job_async.delay(job_id)

    # Raise Retry to reschedule this cover letter task
    raise Retry(
        message=f"Job {job_id} analysis in progress, retrying in 30s",
        countdown=30,  # Retry after 30 seconds
    )


async def _analyze_resume(
    resume_document: Document,
    ctx: GatewayContext,
) -> AnalyzedResume:
    """Run resume_analyzer agent."""
    result = await AgentGateway.get().call(
        agent_id="resume_analyzer",
        input_data=resume_document.content,
        context={**ctx, "operation": "resume_analysis"},
    )
    if isinstance(result, AnalyzedResume):
        return result
    return AnalyzedResume(**result)


async def _generate_with_review(
    application: Application,
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    ctx: GatewayContext,
) -> tuple[str, Optional[ReviewResult]]:
    """Generate draft, review, and iterate up to MAX_REVIEW_ITERATIONS."""
    feedback: str = ""
    last_review: Optional[ReviewResult] = None

    for attempt in range(MAX_REVIEW_ITERATIONS):
        writer_input = _build_writer_prompt(
            job_analysis=job_analysis,
            resume_analysis=resume_analysis,
            tailoring_level=application.tailoring_level,
            feedback=feedback,
        )
        draft_output = await AgentGateway.get().call(
            agent_id="cover_letter_writer",
            input_data=writer_input,
            context={
                **ctx, "operation": f"cover_letter_generate_attempt_{attempt+1}"},
        )
        draft = draft_output if isinstance(
            draft_output, CoverLetterDraft) else CoverLetterDraft(**draft_output)
        draft_text = _render_cover_letter(draft)

        review_input = _build_reviewer_input(
            draft_text=draft_text,
            job_analysis=job_analysis,
            tailoring_level=application.tailoring_level,
        )
        review_output = await AgentGateway.get().call(
            agent_id="reviewer",
            input_data=review_input,
            context={
                **ctx, "operation": f"cover_letter_review_attempt_{attempt+1}"},
        )
        last_review = review_output if isinstance(
            review_output, ReviewResult) else ReviewResult(**review_output)

        if (not last_review.needs_revision) and (last_review.overall_score >= REVIEW_PASS_SCORE):
            return draft_text, last_review

        feedback = _build_feedback(last_review)

    # Return last attempt even if review not passing
    return draft_text, last_review


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
