"""Resume tailoring logic using AgentGateway."""
from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.gateway import AgentGateway
from app.core.llm.types import GatewayContext
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.resumes.models import Document, DocumentFormat
from app.modules.resumes.repository import ResumeRepository
from app.modules.resumes.service import ResumeService

logger = logging.getLogger(__name__)


async def run_resume_tailoring(
    db: AsyncSession,
    application_id: str,
    resume_id: str,
    job_id: int,
    tailoring_level: str,
    workflow_id: str,
    task_id: str
) -> dict:
    """
    Execute resume tailoring task.
    
    1. Fetch Job Analysis and Source Resume.
    2. Call LLM to tailor resume content.
    3. Save tailored resume as new Document.
    4. Link to Application.
    """
    ctx: GatewayContext = {
        "db": db,
        "workflow_id": workflow_id,
        "task_id": task_id,
        "operation": "resume_tailoring",
    }
    
    # 1. Gather Context
    job_analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not job_analysis:
        raise ValueError(f"Job analysis not found for job {job_id}")

    # Helper to convert SQL model to Pydantic if needed, or just use properties
    # Assuming job_analysis is the SQL model, accessing fields directly works.

    source_resume = await ResumeRepository.get_with_document(db, resume_id)
    if not source_resume or not source_resume.document:
        raise ValueError(f"Source resume document not found for {resume_id}")

    source_content = source_resume.document.content
    
    # 2. Call LLM (using a generic 'resume_tailor' agent or 'content_writer')
    # We construct a prompt manually if no specific schema is enforced yet.
    
    prompt_input = _build_tailoring_prompt(
        source_content=source_content,
        job_analysis=job_analysis,
        tailoring_level=tailoring_level
    )

    # Use 'resume_writer' or similar if available, otherwise 'gpt-4o'
    # Assuming 'resume_tailor' is a configured agent.
    tailored_content = await AgentGateway.get().call(
        agent_id="resume_tailor", # Monitor if this agent exists, otherwise might fail
        input_data=prompt_input,
        context=ctx
    )
    
    # Handle response: explicit content or dict
    if isinstance(tailored_content, dict) and "content" in tailored_content:
        final_content = tailored_content["content"]
    else:
        final_content = str(tailored_content)

    # 3. Create Document
    doc_id = str(uuid4())
    tailored_doc = Document(
        id=doc_id,
        root_id=source_resume.document.root_id or source_resume.document.id,
        parent_id=source_resume.document.id,
        format=DocumentFormat.MARKDOWN,
        content=final_content,
        content_hash=ResumeService._calculate_content_hash(final_content),
        change_comments=f"Tailored for Job {job_id} ({tailoring_level})",
        extra_metadata={"application_id": application_id, "job_id": job_id},
        created_by=source_resume.user_id
    )
    db.add(tailored_doc)
    
    # 4. Update Application
    application = await ApplicationRepository.get_by_id(db, application_id)
    if application:
        application.resume_document_id = doc_id
    
    await db.commit()
    
    return {"tailored_resume_document_id": doc_id}


def _build_tailoring_prompt(
    source_content: str,
    job_analysis: any, # AnalyzedJob model
    tailoring_level: str
) -> str:
    """Construct prompt for resume tailoring."""
    
    # SAFEGUARD: calling .required_skills on SQL model might fail if they are JSON columns not automatically cast to object
    # Assuming they are JSON columns which SQLAlchemy maps to list/dict in Python.
    
    req_skills = ", ".join(job_analysis.required_skills or [])
    
    return (
        f"Tailoring Level: {tailoring_level}\n\n"
        f"JOB REQUIREMENTS:\n"
        f"Skills: {req_skills}\n"
        f"Keywords: {', '.join(job_analysis.company_culture_keywords or [])}\n\n"
        f"ORIGINAL RESUME:\n{source_content}\n\n"
        f"INSTRUCTIONS:\n"
        f"Rewrite the resume content in Markdown to highlight experience relevant to the job requirements.\n"
        f"Do not invent facts. Emphasize matching skills and achievements.\n"
        f"Maintain the same structure but optimize wording."
    )
