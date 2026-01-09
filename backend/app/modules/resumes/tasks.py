"""Celery tasks for resume analysis."""

from app.core.celery_app import celery_app
from app.core.llm.gateway import AgentGateway
from app.modules.resumes.repository import ResumeRepository
from app.modules.resumes.service import ResumeService
from app.modules.workflow import DBTrackingTask
from app.modules.workflow.service import TaskService, TaskSubmissionSpec
from app.shared.enums import TaskType
from agent_configs.schemas import AnalyzedResume


@celery_app.task(base=DBTrackingTask, bind=True)
async def analyze_resume_task(
    self,
    resume_id: str,
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
            "task_id": task_id,
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

    # Extract and save skills
    technical_skills = analysis_data.get("technical_skills", [])
    skills_updated, skills_deleted = 0, 0

    if technical_skills:
        # Save skills to resume_skills table
        skills_updated, skills_deleted = await ResumeService.update_resume_skills(
            db=self.db,
            resume_id=resume_id,
            user_id=resume.user_id,
            skills=technical_skills
        )

    await self.db.commit()

    # Return output data for downstream tasks to decide execution
    return {
        "output_data": {
            "status": "completed",
            "resume_id": resume_id,
            "is_draft": resume.is_draft,
            "skills_updated": skills_updated,
            "skills_deleted": skills_deleted,
        }
    }
