"""Repository for application status history."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import ApplicationStatusHistory
from app.shared.enums import ApplicationStatus


class StatusHistoryRepository:
    """Data access helpers for ApplicationStatusHistory."""

    @staticmethod
    async def append(
        db: AsyncSession,
        application_id: str,
        from_status: ApplicationStatus | None,
        to_status: ApplicationStatus,
        changed_by_id: int | None,
        note: str | None = None,
        changed_at: datetime | None = None,
    ) -> ApplicationStatusHistory:
        """Insert a new status history entry and flush (caller commits)."""
        entry = ApplicationStatusHistory(
            id=str(uuid4()),
            application_id=application_id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            changed_at=changed_at or datetime.now(timezone.utc),
            changed_by_id=changed_by_id,
            note=note,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_for_application(
        db: AsyncSession,
        application_id: str,
    ) -> list[ApplicationStatusHistory]:
        """Return all history entries for an application, newest first."""
        result = await db.execute(
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id == application_id)
            .order_by(ApplicationStatusHistory.changed_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        history_id: str,
        application_id: str,
    ) -> ApplicationStatusHistory | None:
        """Fetch a single entry, scoped to the given application."""
        result = await db.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.id == history_id,
                ApplicationStatusHistory.application_id == application_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_note(
        db: AsyncSession,
        entry: ApplicationStatusHistory,
        note: str,
    ) -> ApplicationStatusHistory:
        """Overwrite the note on an existing entry and flush."""
        entry.note = note
        await db.flush()
        return entry
