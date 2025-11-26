"""Service layer for application creation and workflow execution."""
from __future__ import annotations
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.pagination import PaginationParams, PaginatedResponse

from app.modules.auth.models import User
from app.modules.jobs.service import JobService
from app.modules.resumes.models import Resume, Document
from app.modules.resumes.service import ResumeService
from app.modules.applications.models import Application
from app.modules.applications.schemas import ApplicationCreateRequest
from app.shared.enums import ApplicationStatus
from app.modules.applications.event_types import (
    ApplicationEventType,
    ApplicationCreatedPayload,
)
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository


class ApplicationService:
    """Business logic for job applications and workflow orchestration."""

    @staticmethod
    async def create_application(
        db: AsyncSession,
        user: User,
        payload: ApplicationCreateRequest,
    ) -> Application:
        """Create application, working resume copy, workflow, and enqueue cover letter generation."""
        # Validate job
        job = await JobService.get_job_by_id(db, payload.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        # Validate resume template ownership
        resume_template = await ResumeService.get_resume_by_id(db, payload.resume_template_id, user.id)
        if not resume_template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Resume template not found")

        # Duplicate guard: return existing active application
        existing = await ApplicationRepository.get_by_user_and_job(db, user.id, payload.job_id)
        if existing:
            return existing

        # Copy resume as working resume for tailoring
        working_document = await ApplicationService._copy_resume_for_application(db, resume_template, user.id)

        # Create application via repository
        application = Application(
            user_id=user.id,
            job_id=payload.job_id,
            source_resume_id=payload.resume_template_id,
            resume_document_id=working_document.id,
            status=ApplicationStatus.PENDING,
            tailoring_level=payload.tailoring_level or "light",
        )
        await ApplicationRepository.create(db, application=application)

        # Emit application_created event (transactional with application insert)
        await OutboxRepository.enqueue_event(
            db,
            event_type=ApplicationEventType.APPLICATION_CREATED.value,
            aggregate_type="application",
            aggregate_id=application.id,
            payload=ApplicationCreatedPayload(
                application_id=application.id,
                user_id=user.id,
                job_id=payload.job_id,
                resume_document_id=working_document.id,
                tailoring_level=payload.tailoring_level,
                is_retry=False,
            ).model_dump(),
            meta={"user_id": user.id},
        )

        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def list_applications(
        db: AsyncSession,
        user: User,
        params: PaginationParams,
    ) -> PaginatedResponse[Application]:
        """List applications for the current user with pagination helpers."""
        items, total = await ApplicationRepository.list_for_user(db, user.id, params)

        return PaginatedResponse.create(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    @staticmethod
    async def get_application_by_id(
        db: AsyncSession,
        application_id: str,
        user: User,
    ) -> Optional[Application]:
        """Fetch application by id for current user."""
        return await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)

    @staticmethod
    async def retry_cover_letter(
        db: AsyncSession,
        application_id: str,
        user: User,
    ) -> Application:
        """Retry cover letter generation for failed applications."""
        application = await ApplicationService.get_application_by_id(db, application_id, user)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        if application.status != ApplicationStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only failed applications can be retried",
            )

        # Reset status and emit a fresh application_created event for reprocessing
        await ApplicationRepository.mark_pending(db, application)

        await OutboxRepository.enqueue_event(
            db,
            event_type=ApplicationEventType.APPLICATION_CREATED.value,
            aggregate_type="application",
            aggregate_id=application.id,
            payload=ApplicationCreatedPayload(
                application_id=application.id,
                user_id=user.id,
                job_id=application.job_id,
                resume_document_id=application.resume_document_id,
                tailoring_level=application.tailoring_level,
                is_retry=True,
            ).model_dump(),
            meta={"user_id": application.user_id},
        )

        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def _copy_resume_for_application(
        db: AsyncSession,
        template_resume: Resume,
        user_id: int,
    ) -> Document:
        """Copy resume template into a new working document for application tailoring."""
        source_doc = template_resume.document
        new_doc_id = str(uuid4())
        new_document = Document(
            id=new_doc_id,
            root_id=new_doc_id,
            parent_id=source_doc.id,
            format=source_doc.format,
            content=source_doc.content,
            content_hash=ResumeService._calculate_content_hash(
                source_doc.content),
            change_comments="Copied for application tailoring",
            extra_metadata=source_doc.extra_metadata or {},
            created_by=user_id,
        )
        db.add(new_document)
        await db.flush()
        return new_document

    @staticmethod
    async def _load_application_for_processing(db: AsyncSession, application_id: str) -> Optional[Application]:
        """Load application with dependencies needed for processing."""
        return await ApplicationRepository.get_with_dependencies(db, application_id)
