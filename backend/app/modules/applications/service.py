"""Service layer for application creation and workflow execution."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import BadRequestError, NotFoundError, JobPilotException
from app.modules.applications.models import Application
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.schemas import ApplicationCreateRequest, ApplicationRetryRequest
from app.modules.auth.models import User
from app.modules.jobs.service import JobService
from app.modules.resumes.models import Document, Resume
from app.modules.resumes.repository import DocumentRepository
from app.modules.resumes.service import ResumeService
from app.shared.schemas import DocumentEditResponse, DocumentUpdateRequest
from app.shared.enums import (
    ApplicationResolution,
    ApplicationStatus,
    EntityType,
    TailoringLevel,
    TaskType,
)
from app.shared.pagination import PaginatedResponse, PaginationParams
from app.modules.workflow.service import TaskService, TaskSubmissionSpec


class ApplicationService:
    """Business logic for job applications and workflow orchestration."""

    MANUAL_RESOLUTION_TRANSITIONS: dict[ApplicationResolution, set[ApplicationResolution]] = {
        ApplicationResolution.ACTIVE: {
            ApplicationResolution.JOB_CLOSED,
            ApplicationResolution.USER_SKIPPED,
        },
        ApplicationResolution.JOB_CLOSED: set(),
        ApplicationResolution.USER_SKIPPED: set(),
        ApplicationResolution.STALE_NO_RESPONSE: set(),
    }
    RESOLUTION_ALLOWED_STATUSES: set[ApplicationStatus] = {
        ApplicationStatus.PENDING,
        ApplicationStatus.TAILORING,
        ApplicationStatus.READY,
    }
    ALLOWED_STATUS_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
        ApplicationStatus.PENDING: {ApplicationStatus.TAILORING},
        ApplicationStatus.TAILORING: {ApplicationStatus.READY, ApplicationStatus.FAILED},
        ApplicationStatus.READY: {ApplicationStatus.APPLIED, ApplicationStatus.FAILED},
        ApplicationStatus.APPLIED: {ApplicationStatus.PHONE_SCREEN, ApplicationStatus.REJECTED},
        ApplicationStatus.PHONE_SCREEN: {ApplicationStatus.INTERVIEWING, ApplicationStatus.REJECTED},
        ApplicationStatus.INTERVIEWING: {ApplicationStatus.OFFER, ApplicationStatus.REJECTED},
        ApplicationStatus.OFFER: set(),
        ApplicationStatus.REJECTED: set(),
        ApplicationStatus.FAILED: {ApplicationStatus.PENDING},
    }

    @staticmethod
    def _append_status_history(
        application: Application,
        from_status: ApplicationStatus,
        to_status: ApplicationStatus,
        operator_user_id: int,
        note: str | None = None,
    ) -> None:
        """Append status transition record into tailoring_progress JSON."""
        progress = dict(application.tailoring_progress or {})
        history = list(progress.get("status_history", []))
        history.append(
            {
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "from_status": from_status.value,
                "to_status": to_status.value,
                "operator_user_id": operator_user_id,
                "note": note,
            }
        )
        progress["status_history"] = history
        application.tailoring_progress = progress

    @staticmethod
    def _append_resolution_history(
        application: Application,
        from_resolution: ApplicationResolution,
        to_resolution: ApplicationResolution,
        operator_user_id: int,
        note: str | None = None,
    ) -> None:
        """Append resolution transition record into tailoring_progress JSON."""
        progress = dict(application.tailoring_progress or {})
        history = list(progress.get("resolution_history", []))
        history.append(
            {
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "from_resolution": from_resolution.value,
                "to_resolution": to_resolution.value,
                "operator_user_id": operator_user_id,
                "note": note,
            }
        )
        progress["resolution_history"] = history
        application.tailoring_progress = progress

    @staticmethod
    async def update_status(
        db: AsyncSession,
        application_id: str,
        user: User,
        target_status: ApplicationStatus,
        note: str | None = None,
    ) -> Application:
        """Update application status with guarded state transitions."""
        application = await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)
        if not application:
            raise NotFoundError("Application not found")

        current_status = application.status
        if current_status == target_status:
            raise BadRequestError("Application is already in the target status")

        if application.resolution != ApplicationResolution.ACTIVE:
            raise BadRequestError(
                f"Cannot change status while application resolution is {application.resolution.value}. "
                "Only active applications can advance in the pipeline."
            )

        allowed_targets = ApplicationService.ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_targets:
            allowed_labels = ", ".join(status.value for status in sorted(allowed_targets, key=lambda x: x.value))
            message = (
                f"Invalid status transition: {current_status.value} -> {target_status.value}. "
                f"Allowed next statuses: {allowed_labels or 'none'}."
            )
            raise BadRequestError(message)

        ApplicationService._append_status_history(
            application=application,
            from_status=current_status,
            to_status=target_status,
            operator_user_id=user.id,
            note=note,
        )
        application.status = target_status
        now = datetime.now(timezone.utc)
        if target_status == ApplicationStatus.APPLIED and application.applied_at is None:
            application.applied_at = now
        if target_status == ApplicationStatus.OFFER and application.offered_at is None:
            application.offered_at = now
        application.updated_at = now
        if target_status != ApplicationStatus.FAILED:
            application.last_error = None

        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def update_resolution(
        db: AsyncSession,
        application_id: str,
        user: User,
        target_resolution: ApplicationResolution,
        note: str | None = None,
    ) -> Application:
        """Update application resolution with guarded transitions."""
        application = await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)
        if not application:
            raise NotFoundError("Application not found")

        current_resolution = application.resolution
        if current_resolution == target_resolution:
            raise BadRequestError("Application is already in the target resolution")

        if target_resolution == ApplicationResolution.STALE_NO_RESPONSE:
            raise BadRequestError("STALE_NO_RESPONSE is reserved for future automatic workflows")

        if application.status not in ApplicationService.RESOLUTION_ALLOWED_STATUSES:
            allowed_labels = ", ".join(
                sorted(status.value for status in ApplicationService.RESOLUTION_ALLOWED_STATUSES)
            )
            raise BadRequestError(
                f"Resolution can only be changed for pre-submit applications. "
                f"Allowed statuses: {allowed_labels}."
            )

        allowed_targets = ApplicationService.MANUAL_RESOLUTION_TRANSITIONS.get(current_resolution, set())
        if target_resolution not in allowed_targets:
            allowed_labels = ", ".join(
                resolution.value for resolution in sorted(allowed_targets, key=lambda x: x.value)
            )
            raise BadRequestError(
                f"Invalid resolution transition: {current_resolution.value} -> {target_resolution.value}. "
                f"Allowed next resolutions: {allowed_labels or 'none'}."
            )

        now = datetime.now(timezone.utc)
        ApplicationService._append_resolution_history(
            application=application,
            from_resolution=current_resolution,
            to_resolution=target_resolution,
            operator_user_id=user.id,
            note=note,
        )
        application.resolution = target_resolution
        application.resolved_at = now
        application.resolution_note = note
        application.updated_at = now

        if target_resolution == ApplicationResolution.JOB_CLOSED:
            job = application.job
            if not job:
                raise NotFoundError("Job not found")
            job.manual_expired = True
            job.manual_expired_by = user.id
            job.manual_expired_at = now
            job.manual_expired_note = note

        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def get_tailored_resume_for_edit(
        db: AsyncSession, application_id: str, user: User
    ) -> DocumentEditResponse:
        """Get tailored resume document for unified editor."""
        application = await ApplicationRepository.get_with_dependencies(db, application_id)
        if not application or application.user_id != user.id:
            raise NotFoundError("Application not found")

        if not application.resume_document_id:
            raise NotFoundError("Tailored resume not generated yet")

        resume_doc = await DocumentRepository.get_by_id(db, application.resume_document_id)
        if not resume_doc:
            raise NotFoundError("Resume document not found")

        job_title = application.job.title if application.job else ""
        company_name = None
        if application.job:
            company_name = getattr(application.job, "company_name", None) or getattr(
                application.job, "advertiser_name", None
            )

        return DocumentEditResponse(
            business_type="tailored_resume",
            business_id=application.id,
            title=f"Resume for {job_title}" if job_title else "Tailored Resume",
            document_id=resume_doc.id,
            content=resume_doc.content,
            format=resume_doc.format,
            created_at=application.created_at,
            updated_at=application.updated_at,
            job_title=job_title or None,
            company_name=company_name,
            source_resume_title=application.source_resume.title if application.source_resume else None,
        )

    @staticmethod
    async def update_resume_content(
        db: AsyncSession,
        application_id: str,
        user: User,
        payload: DocumentUpdateRequest,
    ) -> Application:
        """Update tailored resume content for an application."""
        application = await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)
        if not application:
            raise NotFoundError("Application not found")
        if not application.resume_document_id:
            raise NotFoundError("Resume document not found")

        current_doc = await DocumentRepository.get_by_id(db, application.resume_document_id)
        if not current_doc:
            raise NotFoundError("Resume document not found")
        new_doc = await DocumentRepository.create_new_version(
            db=db,
            parent_document=current_doc,
            content=payload.content,
            created_by=user.id,
            change_comments=payload.change_comments or "Content updated",
        )

        application.resume_document_id = new_doc.id
        application.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(application)
        await db.refresh(new_doc)
        application.resume_document = new_doc

        return application

    @staticmethod
    async def get_cover_letter_for_edit(
        db: AsyncSession, application_id: str, user: User
    ) -> DocumentEditResponse:
        """Get cover letter document for unified editor."""
        application = await ApplicationRepository.get_with_dependencies(db, application_id)
        if not application or application.user_id != user.id:
            raise NotFoundError("Application not found")

        if not application.cover_letter_document_id:
            raise NotFoundError("Cover letter not generated yet")

        cover_letter_doc = await DocumentRepository.get_by_id(db, application.cover_letter_document_id)
        if not cover_letter_doc:
            raise NotFoundError("Cover letter document not found")

        job_title = application.job.title if application.job else ""
        company_name = None
        if application.job:
            company_name = getattr(application.job, "company_name", None) or getattr(
                application.job, "advertiser_name", None
            )

        return DocumentEditResponse(
            business_type="cover_letter",
            business_id=application.id,
            title="Cover Letter",
            document_id=cover_letter_doc.id,
            content=cover_letter_doc.content,
            format=cover_letter_doc.format,
            created_at=application.created_at,
            updated_at=application.updated_at,
            job_title=job_title or None,
            company_name=company_name,
            source_resume_title=application.source_resume.title if application.source_resume else None,
        )

    @staticmethod
    async def update_cover_letter_content(
        db: AsyncSession,
        application_id: str,
        user: User,
        payload: DocumentUpdateRequest,
    ) -> Application:
        """Update cover letter content for an application."""
        application = await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)
        if not application:
            raise NotFoundError("Application not found")
        if not application.cover_letter_document_id:
            raise NotFoundError("Cover letter document not found")

        current_doc = await DocumentRepository.get_by_id(db, application.cover_letter_document_id)
        if not current_doc:
            raise NotFoundError("Cover letter document not found")
        new_doc = await DocumentRepository.create_new_version(
            db=db,
            parent_document=current_doc,
            content=payload.content,
            created_by=user.id,
            change_comments=payload.change_comments or "Content updated",
        )

        application.cover_letter_document_id = new_doc.id
        application.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(application)
        await db.refresh(new_doc)
        application.cover_letter_document = new_doc

        return application

    @staticmethod
    def _sanitize_filename(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
        return re.sub(r"_+", "_", cleaned).strip("_")

    @staticmethod
    def _build_download_filename(user: User, job_title: str | None, label: str) -> str:
        user_part = ApplicationService._sanitize_filename(user.full_name or "") or "User"
        job_part = ApplicationService._sanitize_filename(job_title or "") or "Job"
        label_part = ApplicationService._sanitize_filename(label)

        parts = [user_part]
        if label_part:
            parts.append(label_part)
        parts.append(job_part)
        return f"{'_'.join(parts)}.pdf"

    @staticmethod
    async def export_tailored_resume_to_pdf(
        db: AsyncSession,
        application_id: str,
        user: User,
        template: Optional[str] = None,
        font_size: int = 12,
        include_metadata: bool = False,
    ) -> tuple[bytes, str, str]:
        """Export tailored resume to PDF."""
        from app.modules.resumes.export import DocumentExportService

        application = await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)
        if not application:
            raise NotFoundError("Application not found")
        if not application.resume_document_id:
            raise NotFoundError("Tailored resume not generated yet")

        resume_doc = await DocumentRepository.get_by_id(db, application.resume_document_id)
        if not resume_doc:
            raise NotFoundError("Resume document not found")

        job_title = application.job.title if application.job else None

        try:
            pdf_bytes, _, template_used = await run_in_threadpool(
                DocumentExportService.export_to_pdf,
                document_type="resume",
                content=resume_doc.content,
                title="Resume",
                template=template,
                font_size=font_size,
                include_metadata=include_metadata,
            )
        except ValueError as exc:
            raise BadRequestError(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            raise JobPilotException(str(exc))

        filename = ApplicationService._build_download_filename(
            user=user,
            job_title=job_title,
            label="Resume",
        )
        return pdf_bytes, filename, template_used

    @staticmethod
    async def export_cover_letter_to_pdf(
        db: AsyncSession,
        application_id: str,
        user: User,
        template: Optional[str] = None,
        font_size: int = 12,
        include_metadata: bool = False,
    ) -> tuple[bytes, str, str]:
        """Export cover letter to PDF."""
        from app.modules.resumes.export import DocumentExportService

        application = await ApplicationRepository.get_by_id_for_user(db, application_id, user.id)
        if not application:
            raise NotFoundError("Application not found")
        if not application.cover_letter_document_id:
            raise NotFoundError("Cover letter not generated yet")

        cover_letter_doc = await DocumentRepository.get_by_id(db, application.cover_letter_document_id)
        if not cover_letter_doc:
            raise NotFoundError("Cover letter document not found")

        job_title = application.job.title if application.job else None

        try:
            pdf_bytes, _, template_used = await run_in_threadpool(
                DocumentExportService.export_to_pdf,
                document_type="cover_letter",
                content=cover_letter_doc.content,
                title="Cover Letter",
                template=template,
                font_size=font_size,
                include_metadata=include_metadata,
            )
        except ValueError as exc:
            raise BadRequestError(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            raise JobPilotException(str(exc))

        filename = ApplicationService._build_download_filename(
            user=user,
            job_title=job_title,
            label="CoverLetter",
        )
        return pdf_bytes, filename, template_used

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
            return await ApplicationRepository.get_by_id_for_user(db, existing.id, user.id)

        working_document = await ApplicationService._copy_resume_for_application(
            db, resume_template, user.id
        )

        application = Application(
            user_id=user.id,
            job_id=payload.job_id,
            source_resume_id=payload.resume_template_id,
            resume_document_id=working_document.id,
            status=ApplicationStatus.PENDING,
            tailoring_level=payload.tailoring_level,
            tailoring_progress={"steps": {}, "current_step": "created"}
        )
        await ApplicationRepository.create(db, application=application)
        
        await ApplicationService._submit_initialization_task(
            db=db,
            application=application,
            user_id=user.id,
            tailoring_level=payload.tailoring_level
        )

        await db.commit()
        await db.refresh(application)
        # Ensure job is attached to avoid lazy-load during response serialization
        application.job = job
        return application

    @staticmethod
    async def list_applications(
        db: AsyncSession,
        user: User,
        params: PaginationParams,
        keyword: str | None = None,
        status: ApplicationStatus | None = None,
        status_group: str | None = None,
        resolution: ApplicationResolution | None = ApplicationResolution.ACTIVE,
    ) -> PaginatedResponse[Application]:
        """List applications for the current user with pagination helpers."""
        if status_group and status_group != "in_progress":
            raise BadRequestError("Unsupported status_group filter")
        items, total = await ApplicationRepository.list_for_user(
            db,
            user.id,
            params,
            keyword=keyword,
            status=status,
            status_group=status_group,
            resolution=resolution,
        )

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
    async def get_application_by_job_id(
        db: AsyncSession, user: User, job_id: int
    ) -> Optional[Application]:
        """Fetch application by job_id for current user."""
        return await ApplicationRepository.get_by_user_and_job(db, user.id, job_id)

    @staticmethod
    async def retry_application_tailor(
        db: AsyncSession, application_id: str, user: User, payload: ApplicationRetryRequest
    ) -> Application:
        """Retry application workflow."""
        application = await ApplicationService.get_application_by_id(db, application_id, user)
        if not application:
            raise NotFoundError("Application not found")
        if application.resolution != ApplicationResolution.ACTIVE:
            raise BadRequestError(
                f"Cannot retry application while resolution is {application.resolution.value}. "
                "Only active applications can be retried."
            )
        selected_tailoring_level = payload.tailoring_level or application.tailoring_level

        target_resume_id = payload.resume_template_id or application.source_resume_id
        resume_template = await ResumeService.get_resume_by_id(db, target_resume_id, user.id)
        if not resume_template:
            raise NotFoundError("Resume template not found")
        if resume_template.is_draft:
            raise BadRequestError("Draft resume cannot be used as template")

        previous_resume_document: Optional[Document] = None
        if application.resume_document_id:
            previous_resume_document = await DocumentRepository.get_by_id(
                db, application.resume_document_id
            )
            if not previous_resume_document:
                raise NotFoundError("Current application resume document not found")

        # Keep a full document history on retry:
        # create a new working document from selected template, and link it to previous document.
        retry_working_document = await ApplicationService._copy_resume_for_application(
            db=db,
            template_resume=resume_template,
            user_id=user.id,
            parent_document=previous_resume_document,
            change_comments="Retry: Copied template for application tailoring",
        )
        application.source_resume_id = resume_template.id
        application.resume_document_id = retry_working_document.id

        await ApplicationRepository.mark_pending(db, application)
        application.tailoring_level = selected_tailoring_level

        # Reset progress
        application.tailoring_progress = {
            "steps": {},
            "current_step": "retrying",
            "message": "Restarting tailoring and cover letter generation",
        }

        await ApplicationService._submit_generation_tasks(
            db=db,
            application=application,
            user_id=user.id,
            tailoring_level=selected_tailoring_level,
            is_retry=True
        )

        await db.commit()
        await db.refresh(application)
        return application
        
    @staticmethod
    async def _submit_initialization_task(
        db: AsyncSession, 
        application: Application, 
        user_id: int, 
        tailoring_level: TailoringLevel,
        is_retry: bool = False
    ) -> None:
        """Helper to submit the initialization orchestrator task."""
        await TaskService.submit_task(
            db=db,
            task_type=TaskType.APPLICATION_INITIALIZATION,
            entity_type=EntityType.APPLICATION.value,
            entity_id=application.id,
            user_id=user_id,
            input_data={
                "application_id": application.id,
                "job_id": application.job_id,
                "resume_id": application.source_resume_id,
                "tailoring_level": tailoring_level,
                "is_retry": is_retry
            },
        )

    @staticmethod
    async def _submit_generation_tasks(
        db: AsyncSession,
        application: Application,
        user_id: int,
        tailoring_level: TailoringLevel,
        is_retry: bool = False,
    ) -> None:
        """Submit only resume tailoring and cover letter generation tasks."""
        await TaskService.submit_sequential_tasks(
            db=db,
            entity_type=EntityType.APPLICATION.value,
            entity_id=application.id,
            user_id=user_id,
            tasks=[
                TaskSubmissionSpec(
                    task_type=TaskType.RESUME_TAILORING,
                    input_data={
                        "application_id": application.id,
                        "resume_id": application.source_resume_id,
                        "job_id": application.job_id,
                        "tailoring_level": tailoring_level,
                        "is_retry": is_retry,
                    },
                ),
                TaskSubmissionSpec(
                    task_type=TaskType.COVER_LETTER_GENERATION,
                    input_data={
                        "application_id": application.id,
                        "job_id": application.job_id,
                        "is_retry": is_retry,
                    },
                ),
            ],
        )

    @staticmethod
    async def _copy_resume_for_application(
        db: AsyncSession,
        template_resume: Resume,
        user_id: int,
        parent_document: Optional[Document] = None,
        change_comments: str = "Copied for application tailoring",
    ) -> Document:
        """Copy resume template into a new working document for application tailoring."""
        from app.modules.resumes.repository import DocumentRepository

        source_doc = template_resume.document
        new_doc_id = str(uuid4())
        if parent_document:
            root_id = parent_document.root_id
            parent_id = parent_document.id
        else:
            root_id = new_doc_id
            parent_id = source_doc.id

        new_document = Document(
            id=new_doc_id,
            root_id=root_id,
            parent_id=parent_id,
            format=source_doc.format,
            content=source_doc.content,
            content_hash=DocumentRepository._calculate_content_hash(
                source_doc.content),
            change_comments=change_comments,
            extra_metadata=source_doc.extra_metadata or {},
            created_by=user_id,
        )
        await DocumentRepository.create(db, new_document)
        await db.flush()
        return new_document

    @staticmethod
    async def _load_application_for_processing(
        db: AsyncSession, application_id: str
    ) -> Optional[Application]:
        """Load application with dependencies needed for processing."""
        return await ApplicationRepository.get_with_dependencies(db, application_id)
