"""Cover letter generation task logic using AgentGateway + YAML agents."""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from agent_configs.schemas import AnalyzedJob, AnalyzedResume, CoverLetterDraft
from app.core.llm.gateway import AgentGateway
from app.modules.applications.models import Application
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.models import SeekJob
from app.modules.resumes.models import Document, DocumentFormat
from app.modules.resumes.repository import DocumentRepository

logger = logging.getLogger(__name__)


async def run_cover_letter_task(
    db: AsyncSession,
    application: Application,
    task_id: str,
    is_retry: bool = False,
):
    """Execute two-pass cover letter generation via writer and polisher agents."""
    from app.modules.jobs.repository import JobAnalysisRepository
    from app.modules.resumes.repository import ResumeRepository

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
    jd_raw = _build_jd_raw(application.job)

    writer_input = _build_writer_prompt(
        jd_raw=jd_raw,
        job_analysis=job_analysis,
        resume_analysis=resume_analysis,
        tailored_resume_content=tailored_resume_content,
    )
    draft_output = await AgentGateway.get().call(
        agent_id="cover_letter_writer",
        input_data=writer_input,
        context={
            "db": db,
            "task_id": task_id,
            "user_id": application.user_id,
        },
    )
    draft = draft_output if isinstance(draft_output, CoverLetterDraft) else CoverLetterDraft(**draft_output)
    initial_content = (draft.content or "").strip()

    if not initial_content:
        raise ValueError("Cover letter writer returned empty content")

    polished_draft = await _polish_cover_letter(
        db=db,
        application=application,
        task_id=task_id,
        initial_content=initial_content,
        candidate_name=(resume_analysis.candidate_name or "").strip(),
    )
    cover_letter_content = (polished_draft.content or "").strip()
    if not cover_letter_content:
        raise ValueError("Cover letter polisher returned empty content")

    if is_retry:
        logger.info(
            "Retry mode: Generating new cover letter version for application %s",
            application.id,
        )
    else:
        logger.info("Generating cover letter for application %s", application.id)

    if application.cover_letter_document_id:
        parent_doc = await DocumentRepository.get_by_id(db, application.cover_letter_document_id)
        if not parent_doc:
            logger.warning(
                "Previous cover letter document %s not found, creating new root",
                application.cover_letter_document_id,
            )
            parent_doc = None
    else:
        parent_doc = None

    if parent_doc:
        change_comment = (
            f"Retry: AI-generated cover letter for Job {application.job_id}"
            if is_retry
            else f"Updated: AI-generated cover letter for Job {application.job_id}"
        )
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
                "application_id": application.id,
                "job_id": application.job_id,
                "task_id": task_id,
                "polished": True,
            },
            created_by=application.user_id,
        )
        db.add(cover_document)
        logger.info("Created new cover letter root document %s", cover_document.id)

    await ApplicationRepository.mark_ready(
        db,
        application,
        cover_letter_document_id=cover_document.id,
    )

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


async def _polish_cover_letter(
    db: AsyncSession,
    application: Application,
    task_id: str,
    initial_content: str,
    candidate_name: str,
) -> CoverLetterDraft:
    """Run a lightweight second-pass polish to humanize tone without changing facts."""
    polisher_input = _build_polisher_prompt(application, initial_content, candidate_name)
    polished_output = await AgentGateway.get().call(
        agent_id="cover_letter_polisher",
        input_data=polisher_input,
        context={
            "db": db,
            "task_id": task_id,
            "user_id": application.user_id,
        },
    )
    polished_draft = (
        polished_output
        if isinstance(polished_output, CoverLetterDraft)
        else CoverLetterDraft(**polished_output)
    )
    polished_content = (polished_draft.content or "").strip()
    if not polished_content:
        raise ValueError("Cover letter polisher returned empty content")
    return CoverLetterDraft(content=polished_content)


def _build_polisher_prompt(
    application: Application,
    initial_content: str,
    candidate_name: str,
) -> str:
    """Build compact second-pass edit input from first draft and light role context."""
    role_bits: list[str] = []
    job = application.job
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

    role_context = "\n".join(role_bits)
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
