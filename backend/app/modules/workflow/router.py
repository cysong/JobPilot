"""
Workflow API endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.workflow.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/monitoring/workers")
async def get_worker_status(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get real-time status of Celery workers.
    
    Returns details about active workers, running tasks, and queues.
    """
    # Note: access control could be stricter here (e.g. superuser only)
    return TaskService.get_celery_worker_status()
