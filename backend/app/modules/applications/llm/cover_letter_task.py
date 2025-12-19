"""Cover letter generation task logic using AgentGateway + YAML agents."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

import textwrap
from sqlalchemy.ext.asyncio import AsyncSession

from agent_configs.schemas import AnalyzedJob, AnalyzedResume, CoverLetterDraft, ReviewResult
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
from app.modules.resumes.repository import DocumentRepository
from app.modules.resumes.service import ResumeService
from app.modules.applications.config import app_module_settings

logger = logging.getLogger(__name__)


async def run_cover_letter_task(
    db: AsyncSession,
    application: Application,
    task_id: str,
    is_retry: bool = False
):
    """
    Execute cover letter generation task via AgentGateway.

    Always creates a new versioned document.

    Args:
        is_retry: If True, indicates retry attempt (creates new version chain from previous)
    """

    # Fetch pre-calculated analysis
    from app.modules.jobs.repository import JobAnalysisRepository
    from app.modules.resumes.repository import ResumeRepository
    from agent_configs.schemas import AnalyzedJob, AnalyzedResume

    job_analysis_model = await JobAnalysisRepository.get_by_job_id(db, application.job_id)
    if not job_analysis_model:
        raise ValueError(f"Job analysis missing for job {application.job_id}")
    
    # Convert SQL model to Pydantic
    job_analysis = AnalyzedJob(
        required_skills=job_analysis_model.required_skills or [],
        preferred_skills=job_analysis_model.preferred_skills or [],
        certifications=job_analysis_model.certifications or [],
        tech_stack=job_analysis_model.tech_stack or [],
        seniority=job_analysis_model.seniority,
        key_responsibilities=job_analysis_model.key_responsibilities or [],
        experience_years=job_analysis_model.experience_years,
        education_requirement=job_analysis_model.education_requirement,
        soft_skills=job_analysis_model.soft_skills or [],
        company_culture_keywords=job_analysis_model.company_culture_keywords or [],
        hiring_priorities=job_analysis_model.hiring_priorities or [],
    )

    # Use the tailored resume document if available, otherwise fallback (should be available)
    # The application.resume_document_id should have been updated by resume_tailoring_task
    resume_doc = application.resume_document
    if not resume_doc:
         raise ValueError(f"Resume document missing for application {application.id}")
    tailored_resume_content = resume_doc.content or ""

    # We treat the tailored resume content as the input for the writer.
    # We also fetch the STRUCTURAL analysis of the original resume for context (skills etc)
    # Wait, the writer prompt uses `resume_analysis.technical_skills`. 
    # We should fetch the original resume analysis.
    
    source_resume = application.source_resume
    if not source_resume:
        # Fallback query if relationship triggers lazy loading issue or similar, though joined load expected
        source_resume = await ResumeRepository.get_with_document(db, application.source_resume_id)
        
    analysis_data = source_resume.analysis_result
    if not analysis_data:
        raise ValueError(f"Resume analysis missing for resume {application.source_resume_id}")

    resume_analysis = AnalyzedResume(**analysis_data)
    
    # NOTE: The prompts currently rely on 'AnalyzeResume' structure.
    # But we also want to use the TAILORED content.
    # The `_build_writer_prompt` uses `resume_analysis` (skills lists) AND potentially the content.
    # Currently it seems it ONLY uses the analysis structure (skills, achievements).
    # If we want the cover letter to reflect the TAILORED resume, we might need to assume the 
    # Resume Analysis reflects the tailored one OR we just use the original skills but the user 
    # expects the cover letter to align with the new resume.
    # For now, we stick to using the Analysis Object for data points.
    
    cover_letter_content, review_result = await _generate_with_review(
        application=application,
        job_analysis=job_analysis,
        resume_analysis=resume_analysis,
        tailored_resume_content=tailored_resume_content,
        context={
            "db": db,
            "task_id": task_id,
            "user_id": application.user_id
        },
    )

    if is_retry:
        logger.info(f"Retry mode: Generating new cover letter version for application {application.id}")
    else:
        logger.info(f"Generating cover letter for application {application.id}")

    # Determine parent document for versioning
    # If application already has a cover letter, it becomes the parent (for retry)
    # Otherwise, create a new root document (for initial creation)
    if application.cover_letter_document_id:
        parent_doc = await DocumentRepository.get_by_id(db, application.cover_letter_document_id)
        if not parent_doc:
            logger.warning(
                f"Previous cover letter document {application.cover_letter_document_id} not found, creating new root")
            parent_doc = None
    else:
        parent_doc = None

    # Create versioned document
    if parent_doc:
        # Create new version with parent
        change_comment = f"Retry: AI-generated cover letter for Job {application.job_id}" if is_retry else f"Updated: AI-generated cover letter for Job {application.job_id}"

        cover_document = await DocumentRepository.create_new_version(
            db=db,
            parent_document=parent_doc,
            content=cover_letter_content,
            created_by=application.user_id,
            change_comments=change_comment,
            extra_metadata={
                "application_id": application.id,
                "job_id": application.job_id,
                "is_retry": is_retry,
                "task_id": task_id,
                "review_score": review_result.overall_score if review_result else None,
            }
        )

        logger.info(
            f"Created new cover letter version {cover_document.id} "
            f"(parent: {parent_doc.id}, root: {cover_document.root_id}, is_retry: {is_retry})"
        )
    else:
        # Create new root document (first time)
        cover_doc_id = str(uuid4())
        cover_document = Document(
            id=cover_doc_id,
            root_id=cover_doc_id,
            parent_id=None,
            format=DocumentFormat.MARKDOWN,
            content=cover_letter_content,
            content_hash=DocumentRepository._calculate_content_hash(
                cover_letter_content),
            change_comments="AI-generated cover letter",
            extra_metadata={
                "application_id": application.id,
                "job_id": application.job_id,
                "task_id": task_id,
                "review_score": review_result.overall_score if review_result else None,
            },
            created_by=application.user_id,
        )
        db.add(cover_document)

        logger.info(f"Created new cover letter root document {cover_document.id}")

    task_output_data = {
        "cover_letter_document_id": cover_document.id,
        "review_result": review_result.model_dump() if review_result else None,
        "is_retry": is_retry
    }

    await ApplicationRepository.mark_ready(
        db,
        application,
        cover_letter_document_id=cover_document.id,
    )

    return task_output_data





async def _generate_with_review(
    application: Application,
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    tailored_resume_content: str,
    context: GatewayContext,
) -> tuple[str, Optional[ReviewResult]]:
    """Generate draft, review, and iterate up to MAX_REVIEW_ITERATIONS."""
    last_review: Optional[ReviewResult] = None

    for attempt in range(app_module_settings.MAX_REVIEW_ITERATIONS):
        writer_input = _build_writer_prompt(
            job_analysis=job_analysis,
            resume_analysis=resume_analysis,
            tailored_resume_content=tailored_resume_content,
            tailoring_level=application.tailoring_level,
            previous_review=last_review,
        )
        draft_output = await AgentGateway.get().call(
            agent_id="cover_letter_writer",
            input_data=writer_input,
            context=context,
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
            context=context,
        )
        last_review = review_output if isinstance(
            review_output, ReviewResult) else ReviewResult(**review_output)

        if (not last_review.needs_revision) and (last_review.overall_score >= app_module_settings.REVIEW_PASS_SCORE):
            return draft_text, last_review

    # Return last attempt even if review not passing
    return draft_text, last_review


def _render_cover_letter(draft: CoverLetterDraft) -> str:
    """Render CoverLetterDraft to markdown text."""
    body = "\n\n".join(draft.body_paragraphs or [])
    return f"{draft.opening}\n\n{body}\n\n{draft.closing}"


def _build_writer_prompt(
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    tailored_resume_content: str,
    tailoring_level: str,
    previous_review: ReviewResult | None,
) -> str:
    """Compose structured input for cover_letter_writer agent."""
    job_json = job_analysis.model_dump_json(indent=2)
    resume_json = resume_analysis.model_dump_json(indent=2)
    review_json = (
        previous_review.model_dump_json(indent=2) if previous_review else "null"
    )
    resume_excerpt = tailored_resume_content[:4000] if tailored_resume_content else ""
    resume_block = textwrap.indent(resume_excerpt, "  ") if resume_excerpt else "  "

    return (
        f"tailoring_level: {tailoring_level or 'light'}\n"
        f"job_analysis: {job_json}\n"
        f"resume_analysis: {resume_json}\n"
        f"tailored_resume_markdown: |\n{resume_block}\n"
        f"previous_review: {review_json}\n"
    )


def _build_reviewer_input(
    draft_text: str,
    job_analysis: AnalyzedJob,
    tailoring_level: str,
) -> str:
    """Compose input text for reviewer agent."""
    required_skills = ", ".join(job_analysis.required_skills or [])
    preferred_skills = ", ".join(job_analysis.preferred_skills or [])
    soft_skills = ", ".join(job_analysis.soft_skills or [])

    return (
        f"Tailoring level: {tailoring_level or 'light'}\n"
        f"Job required skills: {required_skills}\n"
        f"Job preferred skills: {preferred_skills}\n"
        f"Job soft skills: {soft_skills}\n\n"
        f"Cover letter draft:\n{draft_text}"
    )
