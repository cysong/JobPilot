"""Service layer for application creation and workflow execution."""
from __future__ import annotations
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.pagination import PaginationParams, PaginatedResponse

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.jobs.models import SeekJob
from app.modules.jobs.service import JobService
from app.modules.resumes.models import Resume, Document, DocumentFormat
from app.modules.resumes.service import ResumeService
from app.modules.applications.models import (
    Application,
    WorkflowExecution,
    TaskExecution,
    OutboxEvent,
    AICall,
)
from app.modules.applications.schemas import ApplicationCreateRequest
from app.modules.applications.tasks import generate_cover_letter_task
from app.shared.enums import (
    ApplicationStatus,
    WorkflowStatus,
    TaskStatus,
    AICallStatus,
)
from sqlalchemy.orm import selectinload


class ApplicationService:
    """Business logic for job applications and workflow orchestration."""

    WORKFLOW_TYPE = "application_generation"
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
        existing_query = (
            select(Application)
            .where(
                and_(
                    Application.user_id == user.id,
                    Application.job_id == payload.job_id,
                )
            )
        )
        existing_result = await db.execute(existing_query)
        existing = existing_result.scalar_one_or_none()
        if existing:
            return existing

        # Copy resume as working resume for tailoring
        working_document = await ApplicationService._copy_resume_for_application(db, resume_template, user.id)

        # Create application
        application = Application(
            user_id=user.id,
            job_id=payload.job_id,
            source_resume_id=payload.resume_template_id,
            resume_document_id=working_document.id,
            status=ApplicationStatus.PENDING,
            tailoring_level=payload.tailoring_level or "light"
        )
        db.add(application)
        await db.flush()

        # Create workflow execution record
        workflow = WorkflowExecution(
            workflow_type=ApplicationService.WORKFLOW_TYPE,
            config_version=ApplicationService.WORKFLOW_VERSION,
            user_id=user.id,
            entity_id=application.id,
            status=WorkflowStatus.PENDING,
            input_data={
                "job_id": payload.job_id,
                "resume_document_id": working_document.id,
                "tailoring_level": payload.tailoring_level,
            },
        )
        db.add(workflow)
        await db.flush()

        # Create initial task record (pending)
        task = TaskExecution(
            workflow_id=workflow.id,
            task_name="generate_cover_letter",
            task_type="ai_agent",
            priority="normal",
            status=TaskStatus.PENDING,
            input_data={
                "application_id": application.id,
                "job_id": payload.job_id,
                "resume_document_id": working_document.id,
            },
        )
        db.add(task)

        await db.commit()
        await db.refresh(application)
        await db.refresh(workflow)
        await db.refresh(task)

        # Enqueue Celery task (fire-and-forget)
        try:
            generate_cover_letter_task.delay(
                application_id=application.id,
                workflow_id=workflow.id,
                task_id=task.id,
            )
        except Exception as exc:  # noqa: BLE001
            application.mark_failed(str(exc))
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(exc)
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            await db.commit()

        return application

    @staticmethod
    async def list_applications(
        db: AsyncSession,
        user: User,
        params: PaginationParams,
    ) -> PaginatedResponse[Application]:
        """List applications for the current user with pagination helpers."""
        base_query = select(Application).where(Application.user_id == user.id)
        result = await db.execute(
            base_query
            .options(selectinload(Application.job))
            .order_by(Application.created_at.desc())
            .limit(params.get_limit())
            .offset(params.get_offset())
        )
        items = result.scalars().all()

        total = (
            await db.execute(
                select(func.count()).select_from(base_query.subquery())
            )
        ).scalar_one()

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
        query = (
            select(Application)
            .where(
                and_(
                    Application.id == application_id,
                    Application.user_id == user.id,
                )
            )
            .options(
                selectinload(Application.source_resume).selectinload(
                    Resume.document),
                selectinload(Application.resume_document),
                selectinload(Application.job),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

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

        # Create new workflow + task
        workflow = WorkflowExecution(
            workflow_type=ApplicationService.WORKFLOW_TYPE,
            config_version=ApplicationService.WORKFLOW_VERSION,
            user_id=user.id,
            entity_id=application.id,
            status=WorkflowStatus.PENDING,
            input_data={
                "job_id": application.job_id,
                "source_resume_id": application.source_resume_id,
                "tailoring_level": application.tailoring_level,
            },
        )
        db.add(workflow)
        await db.flush()

        task = TaskExecution(
            workflow_id=workflow.id,
            task_name="generate_cover_letter",
            task_type="ai_agent",
            priority="high",
            status=TaskStatus.PENDING,
            input_data={
                "application_id": application.id,
                "job_id": application.job_id,
                "resume_document_id": application.resume_document_id,
                "force": True,
            },
        )
        db.add(task)

        application.status = ApplicationStatus.TAILORING
        application.last_error = None
        await db.commit()
        await db.refresh(application)
        await db.refresh(task)

        try:
            generate_cover_letter_task.delay(
                application_id=application.id,
                workflow_id=workflow.id,
                task_id=task.id,
            )
        except Exception as exc:  # noqa: BLE001
            await ApplicationService._handle_failure(
                db=db,
                application=application,
                workflow=workflow,
                task=task,
                error=str(exc),
            )
            # Reload failed application state for response
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

        application = await ApplicationService._load_application_for_processing(db, application_id)
        workflow = await db.get(WorkflowExecution, workflow_id)
        task = await db.get(TaskExecution, task_id)

        if not application or not workflow or not task:
            return

        workflow.status = WorkflowStatus.RUNNING
        workflow.celery_task_id = celery_task_id
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.celery_task_id = celery_task_id
        task.worker_id = celery_task_id
        application.status = ApplicationStatus.TAILORING

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

            # Update execution records
            now = datetime.utcnow()
            workflow.status = WorkflowStatus.COMPLETED
            workflow.output_data = {"cover_letter_document_id": cover_doc_id}
            workflow.completed_at = now

            task.status = TaskStatus.SUCCESS
            task.output_data = {"cover_letter_document_id": cover_doc_id}
            task.completed_at = now
            task.execution_time_ms = int(
                (time.perf_counter() - start_time) * 1000)

            application.status = ApplicationStatus.READY
            application.cover_letter_document_id = cover_doc_id
            application.last_error = None

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

            # Outbox event
            outbox = OutboxEvent(
                event_type="application_ready",
                aggregate_type="application",
                aggregate_id=application.id,
                payload={
                    "application_id": application.id,
                    "cover_letter_document_id": cover_doc_id,
                    "status": application.status.value,
                },
                meta={"user_id": application.user_id},
                published=False,
            )
            db.add(outbox)

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
        now = datetime.utcnow()
        workflow.status = WorkflowStatus.FAILED
        workflow.error_message = error
        workflow.completed_at = now

        task.status = TaskStatus.FAILED
        task.error_message = error
        task.completed_at = now

        application.mark_failed(error)

        outbox = OutboxEvent(
            event_type="application_failed",
            aggregate_type="application",
            aggregate_id=application.id,
            payload={
                "application_id": application.id,
                "error": error,
            },
            meta={"user_id": application.user_id},
            published=False,
        )
        db.add(outbox)
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
        query = (
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.job),
                selectinload(Application.resume_document),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

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
