"""
User module API router.

This module contains API endpoints for user skill management.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.users import service
from app.modules.users.schemas import (
    UserSkillCreate,
    UserSkillUpdate,
    UserSkillResponse,
    UserSkillListResponse,
    SkillSyncResponse
)

router = APIRouter(prefix="/skills", tags=["User Skills"])


@router.get("", response_model=UserSkillListResponse)
async def get_user_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get all skills for the current user (deduplicated).

    Returns skills ordered by proficiency level (desc) and skill name (asc).
    """
    skills = await service.get_user_skills(db, current_user.id)

    # Calculate counts
    total = len(skills)
    manual_count = sum(1 for s in skills if s.is_manual)
    auto_count = total - manual_count

    return UserSkillListResponse(
        items=skills,
        total=total,
        manual_count=manual_count,
        auto_count=auto_count
    )


@router.post("", response_model=UserSkillResponse, status_code=status.HTTP_201_CREATED)
async def create_user_skill(
    skill_data: UserSkillCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually add a new skill for the current user.

    The skill will be marked as manually added (is_manual=True).
    """
    try:
        skill = await service.create_user_skill(
            db,
            current_user.id,
            skill_data.skill_name,
            skill_data.proficiency_level
        )
        return skill
    except ValueError as e:
        raise BadRequestError(str(e))


@router.put("/{skill_id}", response_model=UserSkillResponse)
async def update_user_skill(
    skill_id: str,
    skill_data: UserSkillUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a skill's proficiency level.

    This marks the skill as manually edited (is_manual=True).
    """
    try:
        skill = await service.update_user_skill(
            db,
            current_user.id,
            skill_id,
            skill_data.proficiency_level
        )
        return skill
    except ValueError as e:
        raise NotFoundError(str(e))


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_skill(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete a skill.

    Note: This only deletes from user_skills. If the skill exists in resumes,
    it will be re-created on the next aggregation.
    """
    deleted = await service.delete_user_skill(db, current_user.id, skill_id)

    if not deleted:
        raise NotFoundError(f"Skill with ID {skill_id} not found")


@router.post("/sync", response_model=SkillSyncResponse)
async def sync_user_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually trigger skill aggregation for the current user.

    This is mainly for debugging or manual sync purposes.
    Normally, aggregation happens automatically after resume analysis or deletion.
    """
    result = await service.aggregate_user_skills(db, current_user.id)

    return SkillSyncResponse(
        message="Skills synchronized successfully",
        total_skills=result["total_skills"],
        manual_skills=result["manual_skills"],
        auto_skills=result["auto_skills"]
    )
