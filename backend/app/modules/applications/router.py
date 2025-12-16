"""Application APIs for creating and managing job applications."""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.applications.schemas import (
    ApplicationCreateRequest,
    ApplicationDetail,
    ApplicationListResponse,
)
from app.modules.applications.service import ApplicationService
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.shared.pagination import PaginationParams

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    params: Annotated[PaginationParams, Depends()],
):
    """List applications for the current user with pagination."""
    return await ApplicationService.list_applications(db, current_user, params)


@router.post("/", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new application and kick off cover letter generation workflow."""
    application = await ApplicationService.create_application(db, current_user, payload)
    return application


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(
    application_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get application detail for current user."""
    application = await ApplicationService.get_application_by_id(db, application_id, current_user)
    if not application:
        raise NotFoundError("Application not found")
    return application


@router.post("/{application_id}/retry", response_model=ApplicationDetail)
async def retry_application_tailor(
    application_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retry cover letter generation for a failed/stuck application.
    Restart the entire workflow.
    """
    application = await ApplicationService.retry_application_tailor(db, application_id, current_user)
    return application
