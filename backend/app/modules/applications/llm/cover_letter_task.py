"""Cover letter generation task logic using AgentGateway + YAML agents."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from agent_configs.schemas import AnalyzedJob, AnalyzedResume, CoverLetterDraft
from app.core.llm.gateway import AgentGateway
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.models import SeekJob
from app.modules.resumes.models import Document, DocumentFormat
from app.modules.resumes.repository import DocumentRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoverLetterInput:
    """Everything the cover letter calls need, loaded up front (no ORM objects)."""
    application_id: str
    user_id: int
    job_id: int
    cover_letter_document_id: str | None  # previous version (retry) or None
    writer_prompt: str
    role_context: str
    candidate_name: str


async def load_cover_letter_input(db: AsyncSession, application_id: str) -> CoverLetterInput:
    """Load job analysis, tailored resume and resume analysis, and build the writer prompt."""
    from app.modules.jobs.repository import JobAnalysisRepository
    from app.modules.resumes.repository import ResumeRepository

    application = await ApplicationRepository.get_with_dependencies(db, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")

    job_analysis_model = await JobAnalysisRepository.get_by_job_id(db, application.job_id)
    if not job_analysis_model:
        raise ValueError(f"Job analysis missing for job {application.job_id}")

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

    resume_doc = application.resume_document
    if not resume_doc:
        raise ValueError(f"Resume document missing for application {application.id}")
    tailored_resume_content = resume_doc.content or ""

    source_resume = application.source_resume
    if not source_resume:
        source_resume = await ResumeRepository.get_with_document(db, application.source_resume_id)

    analysis_data = source_resume.analysis_result if source_resume else None
    if not analysis_data:
        raise ValueError(f"Resume analysis missing for resume {application.source_resume_id}")

    resume_analysis = AnalyzedResume(**analysis_data)
    return CoverLetterInput(
        application_id=application.id,
        user_id=application.user_id,
        job_id=application.job_id,
        cover_letter_document_id=application.cover_letter_document_id,
        writer_prompt=_build_writer_prompt(
            jd_raw=_build_jd_raw(application.job),
            job_analysis=job_analysis,
            resume_analysis=resume_analysis,
            tailored_resume_content=tailored_resume_content,
        ),
        role_context=_build_role_context(application.job),
        candidate_name=(resume_analysis.candidate_name or "").strip(),
    )


async def call_cover_letter_agents(cover: CoverLetterInput, task_id: str) -> str:
    """Two passes, writer then polisher (no DB session involved). Returns the final text."""
    context = {"task_id": task_id, "user_id": cover.user_id}
    draft_output = await AgentGateway.get().call(
        agent_id="cover_letter_writer",
        input_data=cover.writer_prompt,
        context=dict(context),
    )
    draft = draft_output if isinstance(draft_output, CoverLetterDraft) else CoverLetterDraft(**draft_output)
    initial_content = (draft.content or "").strip()
    if not initial_content:
        raise ValueError("Cover letter writer returned empty content")

    # Lightweight second pass to humanize tone without changing facts.
    polished_output = await AgentGateway.get().call(
        agent_id="cover_letter_polisher",
        input_data=_build_polisher_prompt(cover.role_context, initial_content, cover.candidate_name),
        context=dict(context),
    )
    polished = (
        polished_output if isinstance(polished_output, CoverLetterDraft) else CoverLetterDraft(**polished_output)
    )
    content = (polished.content or "").strip()
    if not content:
        raise ValueError("Cover letter polisher returned empty content")
    return content


async def save_cover_letter(
    db: AsyncSession,
    cover: CoverLetterInput,
    cover_letter_content: str,
    task_id: str,
    is_retry: bool = False,
) -> dict:
    """Save the cover letter (new version or new root) and mark the application READY."""
    application = await ApplicationRepository.get_by_id(db, cover.application_id)
    if not application:
        raise ValueError(f"Application {cover.application_id} not found")

    if is_retry:
        logger.info("Retry mode: Generating new cover letter version for application %s", cover.application_id)
    else:
        logger.info("Generating cover letter for application %s", cover.application_id)

    parent_doc = None
    if cover.cover_letter_document_id:
        parent_doc = await DocumentRepository.get_by_id(db, cover.cover_letter_document_id)
        if not parent_doc:
            logger.warning(
                "Previous cover letter document %s not found, creating new root",
                cover.cover_letter_document_id,
            )

    if parent_doc:
        change_comment = (
            f"Retry: AI-generated cover letter for Job {cover.job_id}"
            if is_retry
            else f"Updated: AI-generated cover letter for Job {cover.job_id}"
        )
        cover_document = await DocumentRepository.create_new_version(
            db=db,
            parent_document=parent_doc,
            content=cover_letter_content,
            created_by=cover.user_id,
            change_comments=change_comment,
            extra_metadata={
                "application_id": cover.application_id,
                "job_id": cover.job_id,
                "is_retry": is_retry,
                "task_id": task_id,
                "polished": True,
            },
        )
        logger.info(
            "Created new cover letter version %s (parent: %s, root: %s, is_retry: %s)",
            cover_document.id,
            parent_doc.id,
            cover_document.root_id,
            is_retry,
        )
    else:
        cover_doc_id = str(uuid4())
        cover_document = Document(
            id=cover_doc_id,
            root_id=cover_doc_id,
            parent_id=None,
            format=DocumentFormat.MARKDOWN,
            content=cover_letter_content,
            content_hash=DocumentRepository._calculate_content_hash(cover_letter_content),
            change_comments="AI-generated cover letter",
            extra_metadata={
                "application_id": cover.application_id,
                "job_id": cover.job_id,
                "task_id": task_id,
                "polished": True,
            },
            created_by=cover.user_id,
        )
        db.add(cover_document)
        logger.info("Created new cover letter root document %s", cover_document.id)

    await ApplicationRepository.mark_ready(
        db,
        application,
        cover_letter_document_id=cover_document.id,
    )
    await db.commit()

    return {
        "cover_letter_document_id": cover_document.id,
        "is_retry": is_retry,
    }


def _build_writer_prompt(
    jd_raw: str,
    job_analysis: AnalyzedJob,
    resume_analysis: AnalyzedResume,
    tailored_resume_content: str,
) -> str:
    """Compose compact structured input for cover_letter_writer agent."""
    job_json = json.dumps(
        _prune_empty_values(job_analysis.model_dump()),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    resume_json = json.dumps(
        _prune_empty_values(resume_analysis.model_dump()),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    resume_excerpt = tailored_resume_content[:6000] if tailored_resume_content else ""

    return (
        f"jd_raw: |\n{jd_raw}\n"
        f"job_analysis: {job_json}\n"
        f"resume_analysis: {resume_json}\n"
        f"tailored_resume_markdown: |\n{resume_excerpt}\n"
    )


def _build_role_context(job: SeekJob | None) -> str:
    """Light role context (title, company, work type) for the polisher."""
    role_bits: list[str] = []
    if job:
        title = (job.title or "").strip()
        company = (job.company_name or job.advertiser_name or "").strip()
        work_types = (job.work_types_label or "").strip()
        if title:
            role_bits.append(f"Job Title: {title}")
        if company:
            role_bits.append(f"Company: {company}")
        if work_types:
            role_bits.append(f"Work Type: {work_types}")
    return "\n".join(role_bits)


def _build_polisher_prompt(role_context: str, initial_content: str, candidate_name: str) -> str:
    """Build compact second-pass edit input from first draft and light role context."""
    return (
        f"role_context: |\n{role_context}\n"
        f"candidate_name: {candidate_name}\n"
        f"draft: |\n{initial_content}\n"
    )

def _build_jd_raw(job: SeekJob | None) -> str:
    """Build rich JD context from original job fields for higher-quality personalization."""
    if not job:
        return ""

    sections: list[str] = []
    title = (job.title or "").strip()
    company = (job.company_name or job.advertiser_name or "").strip()
    abstract = (job.abstract or "").strip()
    content = (job.content or "").strip()
    bullets = (job.product_bullets or "").strip()
    company_desc = (job.company_description or "").strip()
    industry = (job.company_industry or "").strip()
    work_types = (job.work_types_label or "").strip()
    location = (job.location_label or "").strip()

    if title:
        sections.append(f"Job Title: {title}")
    if company:
        sections.append(f"Company: {company}")
    if work_types:
        sections.append(f"Work Type: {work_types}")
    if location:
        sections.append(f"Location: {location}")
    if industry:
        sections.append(f"Industry: {industry}")
    if abstract:
        sections.append(f"Abstract:\n{abstract}")
    if bullets:
        sections.append(f"Highlights:\n{bullets}")
    if company_desc:
        sections.append(f"Company Context:\n{company_desc}")
    if content:
        sections.append(f"Full JD:\n{content}")

    # Keep a large cap to preserve quality while preventing pathological prompt growth.
    return "\n\n".join(sections)[:14000]


def _prune_empty_values(value: Any) -> Any:
    """Recursively remove empty fields to reduce prompt payload size."""
    if isinstance(value, dict):
        pruned: dict[str, Any] = {}
        for key, item in value.items():
            cleaned = _prune_empty_values(item)
            if cleaned is None:
                continue
            if cleaned == "":
                continue
            if isinstance(cleaned, (list, dict)) and not cleaned:
                continue
            pruned[key] = cleaned
        return pruned

    if isinstance(value, list):
        pruned_list = []
        for item in value:
            cleaned = _prune_empty_values(item)
            if cleaned is None:
                continue
            if cleaned == "":
                continue
            if isinstance(cleaned, (list, dict)) and not cleaned:
                continue
            pruned_list.append(cleaned)
        return pruned_list

    return value
