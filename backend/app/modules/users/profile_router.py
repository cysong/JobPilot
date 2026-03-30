"""User profile preference endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.users import service
from app.modules.users.schemas import ProfilePreferencesResponse, ProfilePreferencesUpdate

router = APIRouter(prefix="/users/profile", tags=["User Profile"])


@router.get("/preferences", response_model=ProfilePreferencesResponse)
async def get_profile_preferences(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get persisted profile preferences for the current user."""
    preferences = await service.get_profile_preferences(db, current_user.id)
    return ProfilePreferencesResponse.model_validate(preferences)


@router.patch("/preferences", response_model=ProfilePreferencesResponse)
async def update_profile_preferences(
    payload: ProfilePreferencesUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update persisted profile preferences for the current user."""
    preferences = await service.update_profile_preferences(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )
    return ProfilePreferencesResponse.model_validate(preferences)
