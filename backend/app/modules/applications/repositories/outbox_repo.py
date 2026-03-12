"""Repository helpers for OutboxEvent persistence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import OutboxEvent


class OutboxRepository:
    """Data access helpers for outbox_events."""

    @staticmethod
    async def enqueue_event(
        db: AsyncSession,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict,
        meta: dict | None = None,
        max_retries: int = 3,
    ) -> OutboxEvent:
        event = OutboxEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            meta=meta or {},
            max_retries=max_retries,
            published=False,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def fetch_pending_batch(
        db: AsyncSession,
        *,
        batch_size: int = 100,
    ) -> Iterable[OutboxEvent]:
        query = (
            select(OutboxEvent)
            .where(
                and_(
                    OutboxEvent.published.is_(False),
                    OutboxEvent.retry_count < OutboxEvent.max_retries,
                    or_(
                        OutboxEvent.next_retry_at.is_(None),
                        OutboxEvent.next_retry_at <= datetime.now(timezone.utc),
                    ),
                )
            )
            .order_by(OutboxEvent.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def mark_published(db: AsyncSession, event: OutboxEvent) -> None:
        event.published = True
        event.published_at = datetime.now(timezone.utc)
        await db.flush()

    @staticmethod
    async def mark_retry(
        db: AsyncSession,
        event: OutboxEvent,
        *,
        error_message: str,
    ) -> None:
        event.retry_count += 1
        event.error_message = error_message
        if event.retry_count < event.max_retries:
            delay_seconds = 60 * (2 ** event.retry_count)
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        else:
            event.published = True  # Stop retrying
            event.published_at = datetime.now(timezone.utc)
        await db.flush()
