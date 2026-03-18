"""Application APIs for creating and managing job applications."""
from typing import Annotated

from fastapi import APIRouter, Depends, status, Body, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.applications.schemas import (
    ApplicationCreateRequest,
    ApplicationDetail,
    ApplicationListResponse,
    ApplicationResolutionUpdateRequest,
    ApplicationRetryRequest,
    ApplicationStatusUpdateRequest,
)
from app.modules.applications.service import ApplicationService
from app.modules.resumes.schemas import ResumeExportRequest
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.shared.schemas import DocumentEditResponse, DocumentUpdateRequest
from app.shared.pagination import PaginationParams
from app.shared.enums import ApplicationResolution, ApplicationStatus

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    params: Annotated[PaginationParams, Depends()],
    keyword: str | None = Query(None, description="Search by job title or company"),
    status: ApplicationStatus | None = Query(None, description="Filter by application status"),
    resolution: ApplicationResolution | None = Query(
        ApplicationResolution.ACTIVE,
        description="Filter by application resolution; defaults to ACTIVE",
    ),
):
    """List applications for the current user with pagination."""
    return await ApplicationService.list_applications(
        db,
        current_user,
        params,
        keyword=keyword,
        status=status,
        resolution=resolution,
    )


@router.post("/", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new application and kick off cover letter generation workflow."""
    application = await ApplicationService.create_application(db, current_user, payload)
    return application


@router.get("/{application_id}/resume/edit", response_model=DocumentEditResponse)
async def get_tailored_resume_for_edit(
    application_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get tailored resume document for unified editor."""
    return await ApplicationService.get_tailored_resume_for_edit(db, application_id, current_user)


@router.patch("/{application_id}/resume", response_model=ApplicationDetail)
async def update_tailored_resume(
    application_id: str,
    payload: DocumentUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update tailored resume content (new document version)."""
    return await ApplicationService.update_resume_content(db, application_id, current_user, payload)


@router.get("/{application_id}/cover-letter/edit", response_model=DocumentEditResponse)
async def get_cover_letter_for_edit(
    application_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get cover letter document for unified editor."""
    return await ApplicationService.get_cover_letter_for_edit(db, application_id, current_user)


@router.patch("/{application_id}/cover-letter", response_model=ApplicationDetail)
async def update_cover_letter(
    application_id: str,
    payload: DocumentUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update cover letter content (new document version)."""
    return await ApplicationService.update_cover_letter_content(db, application_id, current_user, payload)




@router.post("/{application_id}/resume/export", response_class=Response)
async def export_tailored_resume_to_pdf(
    application_id: str,
    export_request: ResumeExportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Export tailored resume to PDF."""
    pdf_bytes, filename, template_used = await ApplicationService.export_tailored_resume_to_pdf(
        db=db,
        application_id=application_id,
        user=current_user,
        template=export_request.template,
        font_size=export_request.font_size,
        include_metadata=export_request.include_metadata,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Template-Used": template_used,
        },
    )


@router.post("/{application_id}/cover-letter/export", response_class=Response)
async def export_cover_letter_to_pdf(
    application_id: str,
    export_request: ResumeExportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Export cover letter to PDF."""
    pdf_bytes, filename, template_used = await ApplicationService.export_cover_letter_to_pdf(
        db=db,
        application_id=application_id,
        user=current_user,
        template=export_request.template,
        font_size=export_request.font_size,
        include_metadata=export_request.include_metadata,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Template-Used": template_used,
        },
    )


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
    payload: ApplicationRetryRequest = Body(default_factory=ApplicationRetryRequest),
):
    """
    Retry cover letter generation for a failed/stuck application.
    Restart the entire workflow.
    """
    application = await ApplicationService.retry_application_tailor(
        db, application_id, current_user, payload
    )
    return application


@router.patch("/{application_id}/status", response_model=ApplicationDetail)
async def update_application_status(
    application_id: str,
    payload: ApplicationStatusUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manually update application status with guarded transitions."""
    return await ApplicationService.update_status(
        db=db,
        application_id=application_id,
        user=current_user,
        target_status=payload.status,
        note=payload.note,
    )


@router.patch("/{application_id}/resolution", response_model=ApplicationDetail)
async def update_application_resolution(
    application_id: str,
    payload: ApplicationResolutionUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manually update application resolution with guarded transitions."""
    return await ApplicationService.update_resolution(
        db=db,
        application_id=application_id,
        user=current_user,
        target_resolution=payload.resolution,
        note=payload.note,
    )
