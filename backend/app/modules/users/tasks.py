"""
User-related Celery tasks.

This module contains async tasks for user skill aggregation.
"""
from sqlalchemy import select
from app.core.celery_app import celery_app
from app.modules.workflow.tasks_base import DBTrackingTask
from app.modules.workflow.models import TaskExecution
from app.modules.users.service import aggregate_user_skills
from app.shared.enums import TaskType


@celery_app.task(base=DBTrackingTask, bind=True)
async def aggregate_user_skills_task(self, user_id: int, resume_id: str, task_id: str):
    """
    Conditionally aggregate user skills from resume_skills to user_skills.

    This task checks the output of the previous RESUME_ANALYSIS task to determine
    if aggregation is needed. Aggregation only runs if:
    1. Resume is NOT a draft (is_draft = False)
    2. Skills were updated or deleted (skills_updated > 0 OR skills_deleted > 0)

    This task is part of the resume analysis workflow:
    RESUME_ANALYSIS → SKILL_AGGREGATION → USER_JOB_MATCHING

    Args:
        user_id: The user ID whose skills need to be aggregated
        resume_id: The resume ID that was analyzed
        task_id: Task execution ID for tracking

    Returns:
        dict: Result with aggregation status and skill count
    """
    # Get current task to access depends_on
    current_task = await self.db.get(TaskExecution, task_id)
    if not current_task:
        raise ValueError(f"Task {task_id} not found")

    # Try to get previous task from depends_on (more efficient)
    resume_analysis_task = None
    depends_on = current_task.depends_on or []
    previous_task_id = depends_on[0] if depends_on else None

    if previous_task_id:
        # Direct lookup of previous task
        resume_analysis_task = await self.db.get(TaskExecution, previous_task_id)

    # Scenario 1: Part of resume analysis workflow - check conditions
    if resume_analysis_task and resume_analysis_task.output_data:
        output = resume_analysis_task.output_data
        is_draft = output.get("is_draft", True)
        skills_updated = output.get("skills_updated", 0)
        skills_deleted = output.get("skills_deleted", 0)

        # Check condition: only aggregate if formal resume AND skills changed
        should_aggregate = not is_draft and (
            skills_updated > 0 or skills_deleted > 0)

        if not should_aggregate:
            return {
                "output_data": {
                    "status": "skipped",
                    "reason": f"Condition not met: is_draft={is_draft}, skills_updated={skills_updated}, skills_deleted={skills_deleted}",
                    "user_id": user_id,
                }
            }

    # Scenario 2: Independent execution (e.g., triggered by delete_resume)
    # No previous RESUME_ANALYSIS task found - proceed with aggregation

    # Perform aggregation
    result = await aggregate_user_skills(self.db, user_id)

    return {
        "output_data": {
            "status": "completed",
            "user_id": user_id,
            "resume_id": resume_id,
            "total_skills": result.get("total_skills", 0),
            "manual_skills": result.get("manual_skills", 0),
            "auto_skills": result.get("auto_skills", 0),
        }
    }
