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
from app.modules.resumes.repository import ResumeRepository, DocumentRepository
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

    application = await ApplicationRepository.get_by_id(db, application_id)
    if not application:
         raise ValueError(f"Application {application_id} not found")
         
    # Use the working document (already copied) as the base for tailoring
    # If this is the first tailoring, it's the copy of the source resume.
    # If it's a re-tailoring, it might be the previous tailored version (which is fine, or we could go back to source?)
    # User requirement: "resume content 应该读取的是application.resume_document_id指定的简历内容，因为一开始就已经复制了source_resume"
    
    # We need to load the document content. Application repository might not have eagerly loaded it unless we used get_with_dependencies
    # Let's fetch the document directly using DocumentRepository
    if not application.resume_document_id:
        raise ValueError(f"Application {application_id} has no resume document linked")

    source_doc = await DocumentRepository.get_by_id(db, application.resume_document_id)
    if not source_doc:
        raise ValueError(f"Resume document {application.resume_document_id} not found")

    source_content = source_doc.content
    
    # 2. Call LLM
    prompt_input = _build_tailoring_prompt(
        source_content=source_content,
        job_analysis=job_analysis,
        tailoring_level=tailoring_level
    )

    tailored_content = await AgentGateway.get().call(
        agent_id="resume_tailor",
        input_data=prompt_input,
        context=ctx
    )
    
    if isinstance(tailored_content, dict) and "content" in tailored_content:
        final_content = tailored_content["content"]
    else:
        final_content = str(tailored_content)

    # 3. Create Document
    # New document is a version of the current working document
    # 3. Create Document
    # New document is a version of the current working document
    tailored_doc = await DocumentRepository.create_new_version(
        db=db,
        parent_document=source_doc,
        content=final_content,
        created_by=application.user_id,
        change_comments=f"Tailored for Job {job_id} ({tailoring_level})",
        extra_metadata={"application_id": application_id, "job_id": job_id}
    )
    doc_id = tailored_doc.id
    
    # 4. Update Application
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
