"""Celery tasks for resume analysis."""
import json

from app.core.celery_app import celery_app
from app.core.llm.gateway import AgentGateway
from app.modules.resumes.repository import ResumeRepository
from app.modules.resumes.service import ResumeService
from app.modules.workflow import DBTrackingTask
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

    allowed_target_job_titles = await ResumeService.get_controlled_target_job_titles(self.db)
    result = await AgentGateway.get().call(
        agent_id="resume_analyzer",
        input_data=json.dumps(
            {
                "resume_content": content,
                "allowed_target_job_titles": allowed_target_job_titles,
            },
            ensure_ascii=False,
        ),
        context={
            "db": self.db,
            "task_id": task_id,
            "user_id": resume.user_id,
        },
    )

    analysis_data = result.model_dump() if isinstance(result, AnalyzedResume) else result
    filtered_target_job_titles = await ResumeService.filter_analysis_target_job_titles(
        self.db,
        analysis_data.get("target_job_titles") or [],
    )
    analysis_data["target_job_titles"] = filtered_target_job_titles
    merged_target_job_titles = ResumeService.merge_target_job_titles(
        resume.target_job_titles,
        filtered_target_job_titles,
    )

    await ResumeRepository.update_analysis(
        db=self.db,
        resume_id=resume_id,
        analysis_data=analysis_data,
        analysis_version=AnalyzedResume.__version__,
        merged_target_job_titles=merged_target_job_titles,
    )

    # Extract and save skills
    technical_skills = analysis_data.get("technical_skills", [])
    skills_updated, skills_deleted = 0, 0

    # Always sync resume skills so re-analysis can remove stale rows.
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
