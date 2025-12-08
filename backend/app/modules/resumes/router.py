"""
Resume API endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.resumes import service
from app.modules.resumes.schemas import (
    ResumeCreate,
    ResumeUpdate,
    ResumeTitleUpdate,
    ResumeResponse,
    ResumeListResponse,
    ResumeListItem,
    FormalResumeLimit,
    DocumentVersion,
    ResumeExportRequest,
    ResumeExportResponse,
    ResumeAnalysisResponse,
    WorkflowResponse,
)
from app.modules.resumes.service import FORMAL_RESUME_LIMIT

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(
    resume_data: ResumeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Create a new draft resume.

    - **title**: Resume title (required)
    - **content**: Resume content in Markdown format
    - **format**: Document format (default: Markdown)
    """
    resume = await service.ResumeService.create_resume(db, current_user.id, resume_data)
    return ResumeResponse.model_validate(resume)


@router.get("/", response_model=ResumeListResponse)
async def list_resumes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_deleted: bool = False
):
    """
    Get all resumes for the current user.

    - **include_deleted**: Include soft-deleted resumes (default: false)
    """
    resumes = await service.ResumeService.get_user_resumes(db, current_user.id, include_deleted)

    # Calculate counts
    draft_count = sum(1 for r in resumes if r.is_draft and not r.is_deleted)
    formal_count = sum(1 for r in resumes if not r.is_draft and not r.is_deleted)

    # Convert to list items
    items = []
    for resume in resumes:
        # Create preview (first 200 chars)
        content_preview = resume.document.content[:200] if resume.document else None

        item = ResumeListItem(
            id=resume.id,
            user_id=resume.user_id,
            title=resume.title,
            is_draft=resume.is_draft,
            is_deleted=resume.is_deleted,
            created_at=resume.created_at,
            updated_at=resume.updated_at,
            content_preview=content_preview
        )
        items.append(item)

    return ResumeListResponse(
        items=items,
        total=len(resumes),
        draft_count=draft_count,
        formal_count=formal_count
    )


@router.get("/formal-limit", response_model=FormalResumeLimit)
async def check_formal_resume_limit(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Check formal resume limit for current user.

    Returns the limit, current count, and whether more can be created.
    """
    can_create, current_count = await service.ResumeService.check_formal_resume_limit(db, current_user.id)

    return FormalResumeLimit(
        limit=FORMAL_RESUME_LIMIT,
        current_count=current_count,
        can_create_more=can_create,
        remaining=max(0, FORMAL_RESUME_LIMIT - current_count)
    )


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get resume details by ID.
    """
    resume = await service.ResumeService.get_resume_by_id(db, resume_id, current_user.id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    return ResumeResponse.model_validate(resume)


@router.put("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: str,
    update_data: ResumeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Update resume content (creates new document version).

    - **content**: Updated resume content
    - **change_comments**: Optional description of changes
    """
    resume = await service.ResumeService.update_resume(db, resume_id, current_user.id, update_data)
    return ResumeResponse.model_validate(resume)


@router.patch("/{resume_id}/title", response_model=ResumeResponse)
async def update_resume_title(
    resume_id: str,
    title_data: ResumeTitleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Update resume title (metadata only, doesn't create new version).
    """
    resume = await service.ResumeService.update_resume_title(db, resume_id, current_user.id, title_data.title)
    return ResumeResponse.model_validate(resume)


@router.patch("/{resume_id}/finalize", response_model=ResumeResponse)
async def finalize_resume(
    resume_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Mark resume as formal version (finalize from draft).

    Checks formal resume limit before finalizing.
    """
    resume = await service.ResumeService.finalize_resume(db, resume_id, current_user.id)
    return ResumeResponse.model_validate(resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Soft delete a resume.
    """
    await service.ResumeService.delete_resume(db, resume_id, current_user.id)


@router.get("/{resume_id}/versions", response_model=list[DocumentVersion])
async def get_resume_versions(
    resume_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get all document versions for a resume (version history).

    Returns documents ordered by created_at (newest first).
    """
    versions = await service.ResumeService.get_resume_versions(db, resume_id, current_user.id)

    return [DocumentVersion.model_validate(doc) for doc in versions]


@router.post("/{resume_id}/export", response_class=Response)
async def export_resume_to_pdf(
    resume_id: str,
    export_request: ResumeExportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Export resume to PDF format.

    - **template**: Template name (modern/classic/minimal), uses default if not specified
    - **font_size**: Base font size in pt (10-16)
    - **include_metadata**: Include generation timestamp in footer

    Returns PDF file as binary response with proper headers.
    """
    pdf_bytes, filename, template_used = await service.ResumeService.export_resume_to_pdf(
        db=db,
        resume_id=resume_id,
        user_id=current_user.id,
        template=export_request.template,
        font_size=export_request.font_size,
        include_metadata=export_request.include_metadata
    )

    # Return PDF as response with download headers
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Template-Used": template_used
        }
    )


@router.get("/templates", response_model=list[str])
async def get_available_templates():
    """
    Get list of available PDF templates for resumes.

    Returns list of template names that can be used for resume export.
    """
    from app.modules.resumes.export import DocumentExportService
    return DocumentExportService.get_available_templates("resume")


@router.post("/{resume_id}/analyze", response_model=WorkflowResponse)
async def trigger_resume_analysis(
    resume_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually trigger resume analysis and create workflow.
    """
    workflow = await service.ResumeService.trigger_resume_analysis(
        db=db,
        resume_id=resume_id,
        user_id=current_user.id,
        manual_trigger=True,
    )

    return WorkflowResponse(
        workflow_id=workflow.id,
        status=workflow.status,
        message="Resume analysis started",
    )


@router.get("/{resume_id}/analysis", response_model=ResumeAnalysisResponse)
async def get_resume_analysis(
    resume_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get resume analysis results if available.
    """
    resume = await service.ResumeService.get_resume_analysis(
        db=db,
        resume_id=resume_id,
        user_id=current_user.id,
    )

    return ResumeAnalysisResponse(
        id=resume.id,
        resume_id=resume.id,
        analysis_result=resume.analysis_result,
        analysis_version=resume.analysis_version,
        analyzed_at=resume.analyzed_at,
    )
