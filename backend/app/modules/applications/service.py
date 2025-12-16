"""Service layer for application creation and workflow execution."""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.applications.models import Application
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.schemas import ApplicationCreateRequest
from app.modules.auth.models import User
from app.modules.jobs.service import JobService
from app.modules.resumes.models import Document, Resume
from app.modules.resumes.service import ResumeService
from app.shared.enums import ApplicationStatus
from app.shared.pagination import PaginatedResponse, PaginationParams


class ApplicationService:
    """Business logic for job applications and workflow orchestration."""

    @staticmethod
    async def create_application(
        db: AsyncSession, user: User, payload: ApplicationCreateRequest
    ) -> Application:
        """Create application, working resume copy, and trigger sequential workflow."""
        job = await JobService.get_job_by_id(db, payload.job_id)
        if not job:
            raise NotFoundError("Job not found")

        resume_template = await ResumeService.get_resume_by_id(
            db, payload.resume_template_id, user.id
        )
        if not resume_template:
            raise NotFoundError("Resume template not found")

        existing = await ApplicationRepository.get_by_user_and_job(
            db, user.id, payload.job_id
        )
        if existing:
            return existing

        working_document = await ApplicationService._copy_resume_for_application(
            db, resume_template, user.id
        )

        application = Application(
            user_id=user.id,
            job_id=payload.job_id,
            source_resume_id=payload.resume_template_id,
            resume_document_id=working_document.id,
            status=ApplicationStatus.PENDING,
            tailoring_level=payload.tailoring_level or "light",
            tailoring_progress={"steps": {}, "current_step": "created"}
        )
        await ApplicationRepository.create(db, application=application)
        
        # Trigger Workflow directly via Orchestrator Task
        from app.modules.workflow.service import TaskService
        from app.shared.enums import TaskType
        
        await TaskService.submit_task(
            db=db,
            task_type=TaskType.APPLICATION_INITIALIZATION,
            entity_type="application",
            entity_id=application.id,
            user_id=user.id,
            input_data={
                "application_id": application.id,
                "job_id": payload.job_id,
                "resume_id": payload.resume_template_id,
                "tailoring_level": payload.tailoring_level or "light",
            },
            application_id=application.id,
            job_id=payload.job_id,
            resume_id=payload.resume_template_id,
            tailoring_level=payload.tailoring_level or "light",
        )

        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def list_applications(
        db: AsyncSession, user: User, params: PaginationParams
    ) -> PaginatedResponse[Application]:
        """List applications for the current user with pagination helpers."""
        items, total = await ApplicationRepository.list_for_user(db, user.id, params)

        return PaginatedResponse.create(
            items=items, total=total, page=params.page, page_size=params.page_size
        )

    @staticmethod
    async def get_application_by_id(
        db: AsyncSession, application_id: str, user: User
    ) -> Optional[Application]:
        """Fetch application by id for current user."""
        return await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)

    @staticmethod
    async def retry_cover_letter(
        db: AsyncSession, application_id: str, user: User
    ) -> Application:
        """Retry application workflow."""
        application = await ApplicationService.get_application_by_id(db, application_id, user)
        if not application:
            raise NotFoundError("Application not found")

        # Allow retry if Failed OR Stuck in Tailoring (handled by caller logic usually, but here strict check removed)
        # Assuming UI only calls this on explicit retry action.
        
        await ApplicationRepository.mark_pending(db, application)
        
        # Reset progress
        application.tailoring_progress = {"steps": {}, "current_step": "retrying", "message": "Restarting workflow"}

        from app.modules.workflow.service import TaskService
        from app.shared.enums import TaskType

        await TaskService.submit_task(
            db=db,
            task_type=TaskType.APPLICATION_INITIALIZATION,
            entity_type="application",
            entity_id=application.id,
            user_id=user.id,
            input_data={
                "application_id": application.id,
                "job_id": application.job_id,
                "resume_id": application.source_resume_id,
                "tailoring_level": application.tailoring_level,
                "is_retry": True
            },
            application_id=application.id,
            job_id=application.job_id,
            resume_id=application.source_resume_id,
            tailoring_level=application.tailoring_level,
        )

        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def _copy_resume_for_application(
        db: AsyncSession, template_resume: Resume, user_id: int
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
            content_hash=ResumeService._calculate_content_hash(source_doc.content),
            change_comments="Copied for application tailoring",
            extra_metadata=source_doc.extra_metadata or {},
            created_by=user_id,
        )
        db.add(new_document)
        await db.flush()
        return new_document

    @staticmethod
    async def _load_application_for_processing(
        db: AsyncSession, application_id: str
    ) -> Optional[Application]:
        """Load application with dependencies needed for processing."""
        return await ApplicationRepository.get_with_dependencies(db, application_id)
