"""Celery tasks for resume analysis."""

from app.core.celery_app import celery_app
from app.core.llm.gateway import AgentGateway
from app.modules.resumes.repository import ResumeRepository
from app.modules.users.repository import UserSkillRepository
from app.modules.workflow import DBTrackingTask
from agent_configs.schemas import AnalyzedResume


@celery_app.task(bind=True, base=DBTrackingTask, max_retries=3)
async def analyze_resume_async(
    self,
    resume_id: str,
    workflow_id: str,
    task_id: str,
) -> dict:
    """Analyze a resume using resume_analyzer agent."""
    resume = await ResumeRepository.get_with_document(self.db, resume_id)
    if not resume:
        raise ValueError(f"Resume {resume_id} not found")

    content = resume.document.content if resume.document else ""
    if not content or len(content.strip()) < 50:
        raise ValueError(f"Resume {resume_id} has insufficient content to analyze")

    result = await AgentGateway.get().call(
        agent_id="resume_analyzer",
        input_data=content,
        context={
            "db": self.db,
            "operation": "resume_analysis",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "resume_id": resume_id,
            "user_id": resume.user_id,
        },
    )

    analysis_data = result.model_dump() if isinstance(result, AnalyzedResume) else result

    await ResumeRepository.update_analysis(
        db=self.db,
        resume_id=resume_id,
        analysis_data=analysis_data,
        analysis_version=AnalyzedResume.__version__,
    )

    technical_skills = analysis_data.get("technical_skills", [])
    if technical_skills:
        await UserSkillRepository.upsert_from_resume_analysis(
            db=self.db,
            user_id=resume.user_id,
            skills=technical_skills,
            resume_id=resume_id,
        )

    await self.db.commit()

    return {
        "output_data": {
            "status": "completed",
            "resume_id": resume_id,
            "skills_extracted": len(technical_skills),
        }
    }
