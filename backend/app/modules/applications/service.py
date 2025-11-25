"""Service layer for application creation and workflow execution."""
from __future__ import annotations
import time
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.pagination import PaginationParams, PaginatedResponse

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.jobs.service import JobService
from app.modules.resumes.models import Resume, Document, DocumentFormat
from app.modules.resumes.service import ResumeService
from app.modules.applications.models import (
    Application,
    AICall,
    TaskExecution,
    WorkflowExecution,
)
from app.modules.applications.schemas import ApplicationCreateRequest
from app.shared.enums import (
    ApplicationStatus,
    AICallStatus,
)
from app.modules.applications.event_types import (
    ApplicationEventType,
    ApplicationCreatedPayload,
    ApplicationReadyPayload,
    ApplicationFailedPayload,
)
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.workflow_repo import WorkflowRepository
from app.modules.applications.repositories.task_repo import TaskRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository


class ApplicationService:
    """Business logic for job applications and workflow orchestration."""

    WORKFLOW_VERSION = "v1.0.0"
    COVER_LETTER_PROMPT_ID = "cover_letter_v1"
    COVER_LETTER_MODEL = "deepseek-chat"

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
    async def run_cover_letter_pipeline(
        db: AsyncSession,
        application_id: str,
        workflow_id: str,
        task_id: str,
        celery_task_id: Optional[str] = None,
    ):
        """Execute cover letter generation task, updating workflow/task/application records."""
        start_time = time.perf_counter()

        application = await ApplicationRepository.get_with_dependencies(db, application_id)
        workflow = await WorkflowRepository.get_by_id(db, workflow_id)
        task = await TaskRepository.get_by_id(db, task_id)

        if not application or not workflow or not task:
            return

        await WorkflowRepository.mark_running(
            db,
            workflow,
            celery_task_id=celery_task_id,
        )
        await TaskRepository.mark_running(
            db,
            task,
            celery_task_id=celery_task_id,
            worker_id=celery_task_id,
        )
        await ApplicationRepository.mark_tailoring(db, application)
        await db.commit()

        try:
            cover_letter_content, usage = await ApplicationService._generate_cover_letter(
                job=application.job,
                resume_document=application.resume_document,
                tailoring_level=application.tailoring_level,
            )

            cover_doc_id = str(uuid4())
            cover_document = Document(
                id=cover_doc_id,
                root_id=cover_doc_id,
                parent_id=None,
                format=DocumentFormat.MARKDOWN,
                content=cover_letter_content,
                content_hash=ResumeService._calculate_content_hash(
                    cover_letter_content),
                change_comments="AI-generated cover letter",
                extra_metadata={"application_id": application.id},
                created_by=application.user_id,
            )
            db.add(cover_document)

            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            await WorkflowRepository.mark_completed(
                db,
                workflow,
                output_data={"cover_letter_document_id": cover_doc_id},
            )
            await TaskRepository.mark_success(
                db,
                task,
                output_data={"cover_letter_document_id": cover_doc_id},
                execution_time_ms=execution_time_ms,
            )
            await ApplicationRepository.mark_ready(
                db,
                application,
                cover_letter_document_id=cover_doc_id,
            )

            # Record AI call
            ai_call = AICall(
                workflow_id=workflow.id,
                task_id=task.id,
                user_id=application.user_id,
                model=ApplicationService.COVER_LETTER_MODEL,
                prompt_id=ApplicationService.COVER_LETTER_PROMPT_ID,
                prompt_version=ApplicationService.WORKFLOW_VERSION,
                latency_ms=usage.get("latency_ms"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                status=AICallStatus.SUCCESS,
                meta={"application_id": application.id},
            )
            db.add(ai_call)

            await OutboxRepository.enqueue_event(
                db,
                event_type=ApplicationEventType.APPLICATION_READY.value,
                aggregate_type="application",
                aggregate_id=application.id,
                payload=ApplicationReadyPayload(
                    application_id=application.id,
                    cover_letter_document_id=cover_doc_id,
                    status=application.status.value,
                ).model_dump(),
                meta={"user_id": application.user_id},
            )
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            await ApplicationService._handle_failure(
                db=db,
                application=application,
                workflow=workflow,
                task=task,
                error=str(exc),
            )

    @staticmethod
    async def _handle_failure(
        db: AsyncSession,
        application: Application,
        workflow: WorkflowExecution,
        task: TaskExecution,
        error: str,
    ):
        """Mark workflow/task/application as failed and write outbox event."""
        await WorkflowRepository.mark_failed(db, workflow, error_message=error)
        await TaskRepository.mark_failed(db, task, error_message=error)
        await ApplicationRepository.mark_failed(db, application, error)

        await OutboxRepository.enqueue_event(
            db,
            event_type=ApplicationEventType.APPLICATION_FAILED.value,
            aggregate_type="application",
            aggregate_id=application.id,
            payload=ApplicationFailedPayload(
                application_id=application.id,
                error=error,
            ).model_dump(),
            meta={"user_id": application.user_id},
        )
        await db.commit()

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

    @staticmethod
    async def _generate_cover_letter(
        job: SeekJob,
        resume_document: Document,
        tailoring_level: str,
    ) -> tuple[str, dict]:
        """Call LLM to generate cover letter content."""
        api_key = settings.OPENROUTER_API_KEY or settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("AI API key is not configured")

        base_url = settings.OPENROUTER_API_BASE or settings.OPENAI_API_BASE
        client = OpenAI(api_key=api_key, base_url=base_url)

        messages = [
            {
                "role": "system",
                "content": "You are an assistant that drafts concise, compelling cover letters tailored to the provided job and resume content.",
            },
            {
                "role": "user",
                "content": (
                    f"Tailoring level: {tailoring_level or 'light'}\n"
                    f"Job title: {job.title}\n"
                    f"Company: {job.company_name or job.advertiser_name or 'Unknown'}\n"
                    f"Job summary:\n{(job.abstract or '')[:1500]}\n\n"
                    f"Job description:\n{(job.content or '')[:4000]}\n\n"
                    f"Resume content:\n{resume_document.content[:4000]}"
                ),
            },
        ]

        start_time = time.perf_counter()
        response = client.chat.completions.create(
            model=ApplicationService.COVER_LETTER_MODEL,
            messages=messages,
            temperature=0.6,
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        content = response.choices[0].message.content if response.choices else ""
        usage = response.usage or {}
        usage_payload = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "latency_ms": latency_ms,
        }

        if not content:
            raise RuntimeError(
                "Cover letter generation returned empty content")

        return content, usage_payload
