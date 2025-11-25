"""Batch consumer for application-related Outbox events."""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.outbox_handlers import HANDLERS
from app.modules.applications.repositories.outbox_repo import OutboxRepository
from app.modules.applications.models import OutboxEvent

logger = logging.getLogger(__name__)


async def process_outbox_batch(
    db: AsyncSession,
    *,
    batch_size: int = 100,
) -> Iterable[OutboxEvent]:
    """Fetch a batch of pending events and route to handlers."""
    events = await OutboxRepository.fetch_pending_batch(db, batch_size=batch_size)
    for event in events:
        handler = HANDLERS.get(event.event_type)
        if not handler:
            logger.warning(
                "No handler for event_type=%s (marking published)", event.event_type)
            await OutboxRepository.mark_published(db, event)
            continue

        try:
            await handler(db, event)
            await OutboxRepository.mark_published(db, event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Outbox handler failed for event_id=%s", event.id)
            await OutboxRepository.mark_retry(db, event, error_message=str(exc))

    if events:
        await db.commit()
    return events
