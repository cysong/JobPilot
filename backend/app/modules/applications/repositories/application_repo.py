"""Repository helpers for Application entities."""
from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.applications.models import Application
from app.modules.resumes.models import Resume
from app.shared.enums import ApplicationStatus
from app.shared.pagination import PaginationParams


class ApplicationRepository:
    """Data access helpers for applications."""

    @staticmethod
    async def get_by_user_and_job(db: AsyncSession, user_id: int, job_id: int) -> Application | None:
        query = (
            select(Application)
            .where(and_(Application.user_id == user_id, Application.job_id == job_id))
            .options(selectinload(Application.job))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_for_user(
        db: AsyncSession,
        application_id: str,
        user_id: int,
    ) -> Application | None:
        query = (
            select(Application)
            .where(
                and_(
                    Application.id == application_id,
                    Application.user_id == user_id,
                )
            )
            .options(
                selectinload(Application.source_resume).selectinload(Resume.document),
                selectinload(Application.resume_document),
                selectinload(Application.job),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        application_id: str,
    ) -> Application | None:
        return await db.get(Application, application_id)

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        user_id: int,
        params: PaginationParams,
    ) -> tuple[list[Application], int]:
        base_query = select(Application).where(Application.user_id == user_id)
        result = await db.execute(
            base_query.options(selectinload(Application.job))
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

        return list(items), total

    @staticmethod
    async def create(db: AsyncSession, *, application: Application) -> Application:
        db.add(application)
        await db.flush()
        return application

    @staticmethod
    async def get_with_dependencies(
        db: AsyncSession,
        application_id: str,
    ) -> Application | None:
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
    async def mark_pending(
        db: AsyncSession,
        application: Application,
        *,
        clear_error: bool = True,
    ) -> None:
        application.status = ApplicationStatus.PENDING
        if clear_error:
            application.last_error = None
        await db.flush()

    @staticmethod
    async def mark_failed(db: AsyncSession, application: Application, error: str) -> None:
        application.mark_failed(error)
        await db.flush()

    @staticmethod
    async def mark_ready(
        db: AsyncSession,
        application: Application,
        *,
        cover_letter_document_id: str | None = None,
        resume_document_id: str | None = None,
    ) -> None:
        application.status = ApplicationStatus.READY
        if cover_letter_document_id:
            application.cover_letter_document_id = cover_letter_document_id
        if resume_document_id:
            application.resume_document_id = resume_document_id
        application.last_error = None
        await db.flush()

    @staticmethod
    async def mark_tailoring(db: AsyncSession, application: Application) -> None:
        application.status = ApplicationStatus.TAILORING
        await db.flush()
