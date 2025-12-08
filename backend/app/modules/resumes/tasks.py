"""Celery tasks for resume analysis."""
import asyncio

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import get_db
from app.core.llm.gateway import AgentGateway
from app.modules.resumes.repository import ResumeRepository
from app.modules.users.repository import UserSkillRepository
from app.modules.workflow import task_status_guard
from agent_configs.schemas import AnalyzedResume


@celery_app.task(bind=True, max_retries=3)
def analyze_resume_async(
    self: Task,
    resume_id: str,
    workflow_id: str,
    task_id: str,
) -> dict:
    """
    Analyze a resume using resume_analyzer agent.

    Status management handled by task_status_guard decorator.
    """

    async def _run():
        async for db in get_db():
            return await _execute_resume_analysis(
                db=db,
                resume_id=resume_id,
                workflow_id=workflow_id,
                task_id=task_id,
            )

    return _run_sync(_run())


@task_status_guard(first=True, last=True)
async def _execute_resume_analysis(
    *,
    db: AsyncSession,
    resume_id: str,
    workflow_id: str,
    task_id: str,
) -> dict:
    """Execute resume analysis workflow."""
    resume = await ResumeRepository.get_with_document(db, resume_id)
    if not resume:
        raise ValueError(f"Resume {resume_id} not found")

    content = resume.document.content if resume.document else ""
    if not content or len(content.strip()) < 50:
        raise ValueError(f"Resume {resume_id} has insufficient content to analyze")

    result = await AgentGateway.get().call(
        agent_id="resume_analyzer",
        input_data=content,
        context={
            "db": db,
            "operation": "resume_analysis",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "resume_id": resume_id,
            "user_id": resume.user_id,
        },
    )

    if isinstance(result, AnalyzedResume):
        analysis_data = result.model_dump()
    else:
        analysis_data = result

    await ResumeRepository.update_analysis(
        db=db,
        resume_id=resume_id,
        analysis_data=analysis_data,
        analysis_version=AnalyzedResume.__version__,
    )

    technical_skills = analysis_data.get("technical_skills", [])
    if technical_skills:
        await UserSkillRepository.upsert_from_resume_analysis(
            db=db,
            user_id=resume.user_id,
            skills=technical_skills,
            resume_id=resume_id,
        )

    await db.commit()

    return {
        "task_output_data": {
            "status": "completed",
            "resume_id": resume_id,
            "skills_extracted": len(technical_skills),
        },
        "workflow_output_data": {
            "resume_id": resume_id,
        },
    }


def _run_sync(coro):
    """Run an async coroutine inside Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
