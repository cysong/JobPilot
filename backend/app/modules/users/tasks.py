"""
User-related Celery tasks.

This module contains async tasks for user skill aggregation.
"""
from app.core.celery_app import app
from app.modules.workflow.tasks_base import DBTrackingTask
from app.modules.users.service import aggregate_user_skills


@app.task(base=DBTrackingTask, bind=True)
async def aggregate_user_skills_task(self, user_id: int, task_id: str = None):
    """
    Aggregate user skills from resume_skills to user_skills.

    This task is triggered after:
    1. Resume analysis completes and skills are extracted
    2. A formal resume is deleted

    Args:
        user_id: The user ID whose skills need to be aggregated
        task_id: Optional task execution ID for tracking

    Returns:
        dict: Result with aggregated skill count
    """
    # Call the service function to perform aggregation
    result = await aggregate_user_skills(self.db, user_id)

    return {
        "output_data": {
            "user_id": user_id,
            "total_skills": result.get("total_skills", 0),
            "manual_skills": result.get("manual_skills", 0),
            "auto_skills": result.get("auto_skills", 0),
        }
    }
