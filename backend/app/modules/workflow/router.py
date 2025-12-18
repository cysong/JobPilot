"""
Workflow API endpoints.
"""
from fastapi import APIRouter

from app.shared.enums import TaskType

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/types")
async def get_task_types():
    """List available task types (public)."""
    return [
        {"value": t.value.value, "displayName": t.value.display_name}
        for t in TaskType
    ]
