"""Resume tailoring logic using AgentGateway."""
from __future__ import annotations

import logging
import textwrap

from sqlalchemy.ext.asyncio import AsyncSession

from agent_configs.schemas import AnalyzedJob, TailoredResume
from app.core.llm.gateway import AgentGateway
from app.core.llm.types import GatewayContext
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.resumes.repository import DocumentRepository, ResumeRepository

logger = logging.getLogger(__name__)


async def run_resume_tailoring(
    db: AsyncSession,
    application_id: str,
    resume_id: str,
    job_id: int,
    tailoring_level: str,
    workflow_id: str,
    task_id: str,
    is_retry: bool = False
) -> dict:
    """
    Execute resume tailoring task.

    Always reads from source resume and creates a new versioned document.

    Args:
        resume_id: Source resume ID (not working document ID)
        is_retry: If True, indicates retry attempt (creates new version chain from previous)

    Process:
    1. Fetch Job Analysis and Source Resume.
    2. Call LLM to tailor resume content.
    3. Save tailored resume as new versioned Document.
    4. Update Application to point to new version.
    """
    # 1. Gather Context
    job_analysis_model = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not job_analysis_model:
        raise ValueError(f"Job analysis not found for job {job_id}")
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

    application = await ApplicationRepository.get_by_id(db, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")

    # Always read from source resume (unified logic for both initial and retry)
    source_resume = await ResumeRepository.get_with_document(db, resume_id)
    if not source_resume or not source_resume.document:
        raise ValueError(
            f"Source resume {resume_id} or its document not found")

    source_content = source_resume.document.content

    if is_retry:
        logger.info(
            f"Retry mode: Reading from source resume {resume_id} for application {application_id}")
    else:
        logger.info(
            f"Reading from source resume {resume_id} for application {application_id}")

    # Determine parent document for versioning
    # If application already has a resume document, it becomes the parent (for retry)
    # Otherwise, the source resume document is the parent (for initial creation)
    if application.resume_document_id:
        parent_doc = await DocumentRepository.get_by_id(db, application.resume_document_id)
        if not parent_doc:
            logger.warning(
                f"Previous resume document {application.resume_document_id} not found, using source as parent")
            parent_doc = source_resume.document
    else:
        parent_doc = source_resume.document
    
    # 2. Call LLM
    prompt_input = _build_tailoring_prompt(
        source_content=source_content,
        job_analysis=job_analysis,
        tailoring_level=tailoring_level
    )

    tailored_content = await AgentGateway.get().call(
        agent_id="resume_tailor",
        input_data=prompt_input,
        context={
            "db": db,
            "task_id": task_id,
            "user_id": application.user_id
        },
    )
    
    if isinstance(tailored_content, TailoredResume):
        final_content = tailored_content.content
    elif isinstance(tailored_content, dict) and "content" in tailored_content:
        final_content = tailored_content["content"]
    else:
        final_content = str(tailored_content)

    # 3. Create new versioned Document
    # parent_doc is either the previous tailored version (retry) or source document (initial)
    change_comment = f"Retry: Tailored from source for Job {job_id} ({tailoring_level})" if is_retry else f"Tailored for Job {job_id} ({tailoring_level})"

    tailored_doc = await DocumentRepository.create_new_version(
        db=db,
        parent_document=parent_doc,
        content=final_content,
        created_by=application.user_id,
        change_comments=change_comment,
        extra_metadata={
            "application_id": application_id,
            "job_id": job_id,
            "tailoring_level": tailoring_level,
            "is_retry": is_retry,
            "task_id": task_id
        }
    )
    doc_id = tailored_doc.id

    logger.info(
        f"Created new resume document version {doc_id} "
        f"(parent: {parent_doc.id}, root: {tailored_doc.root_id}, is_retry: {is_retry})"
    )
    
    # 4. Update Application to point to new version
    application.resume_document_id = doc_id

    await db.commit()

    return {
        "output_data": {
            "resume_document_id": doc_id,
            "is_retry": is_retry,
        }
    }


def _build_tailoring_prompt(
    source_content: str,
    job_analysis: AnalyzedJob,
    tailoring_level: str
) -> str:
    """Construct prompt for resume tailoring."""
    
    # SAFEGUARD: calling .required_skills on SQL model might fail if they are JSON columns not automatically cast to object
    # Assuming they are JSON columns which SQLAlchemy maps to list/dict in Python.
    
    req_skills = ", ".join(job_analysis.required_skills or [])
    preferred_skills = ", ".join(job_analysis.preferred_skills or [])
    soft_skills = ", ".join(job_analysis.soft_skills or [])
    culture_keywords = ", ".join(job_analysis.company_culture_keywords or [])
    job_json = job_analysis.model_dump_json(indent=2)
    resume_block = textwrap.indent(source_content[:6000] if source_content else "", "  ")
    
    return (
        f"tailoring_level: {tailoring_level}\n"
        f"job_analysis: {job_json}\n"
        f"source_resume_markdown: |\n{resume_block}\n\n"
        f"Skill highlights (for quick reference):\n"
        f"- Required: {req_skills}\n"
        f"- Preferred: {preferred_skills}\n"
        f"- Soft skills: {soft_skills}\n"
        f"- Culture keywords: {culture_keywords}\n\n"
        f"INSTRUCTIONS:\n"
        f"Rewrite the resume content in Markdown to highlight experience relevant to the job requirements.\n"
        f"Do not invent facts. Emphasize matching skills and achievements.\n"
        f"Maintain the same structure but optimize wording.\n"
    )
