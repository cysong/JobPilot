"""Cover letter generation task logic using AgentGateway + YAML agents."""
from __future__ import annotations

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
        
    analysis_data = source_resume.analysis
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

    task_output_data = {
        "cover_letter_document_id": cover_doc_id,
        "review_result": review_result.model_dump() if review_result else None,
    }

    await ApplicationRepository.mark_ready(
        db,
        application,
        cover_letter_document_id=cover_doc_id,
    )

    return task_output_data





async def _generate_with_review(
    application: Application,
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    tailored_resume_content: str,
    ctx: GatewayContext,
) -> tuple[str, Optional[ReviewResult]]:
    """Generate draft, review, and iterate up to MAX_REVIEW_ITERATIONS."""
    last_review: Optional[ReviewResult] = None

    for attempt in range(MAX_REVIEW_ITERATIONS):
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
