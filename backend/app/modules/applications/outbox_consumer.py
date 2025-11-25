"""Batch consumer for application-related Outbox events."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.modules.applications.config import app_module_settings
from app.modules.applications.outbox_handlers import HANDLERS
from app.modules.applications.repositories.outbox_repo import OutboxRepository
from app.modules.applications.models import OutboxEvent

logger = logging.getLogger(__name__)


async def process_outbox_batch(
    db: AsyncSession,
    *,
    batch_size: int = 100,
) -> Iterable[OutboxEvent]:
    """
    Fetch a batch of pending events and route to handlers with controlled concurrency.

    Uses Semaphore to limit concurrent processing to MAX_CONCURRENT_EVENTS,
    and each event gets its own database session to avoid race conditions.

    Args:
        db: Database session (only used for fetching events)
        batch_size: Maximum number of events to process in one batch

    Returns:
        List of processed events
    """
    start_time = time.perf_counter()

    # Fetch pending events using the provided session
    events = await OutboxRepository.fetch_pending_batch(db, batch_size=batch_size)

    if not events:
        logger.debug("No pending outbox events to process")
        return []

    max_concurrent = app_module_settings.OUTBOX_MAX_CONCURRENT
    logger.info(f"Processing {len(events)} outbox events with max concurrency {max_concurrent}")

    # Create semaphore to limit concurrent processing
    semaphore = asyncio.Semaphore(max_concurrent)

    # Track processing results
    successful_count = 0
    failed_count = 0
    no_handler_count = 0

    async def process_single_event(event: OutboxEvent) -> None:
        """Process a single event with its own database session."""
        nonlocal successful_count, failed_count, no_handler_count

        # Acquire semaphore to limit concurrency
        async with semaphore:
            # Create a new session for this event to avoid race conditions
            async with async_session_factory() as event_db:
                event_start = time.perf_counter()

                handler = HANDLERS.get(event.event_type)
                if not handler:
                    logger.warning(
                        f"No handler for event_type={event.event_type} (event_id={event.id}), marking as published"
                    )
                    await OutboxRepository.mark_published(event_db, event)
                    await event_db.commit()
                    no_handler_count += 1
                    return

                try:
                    logger.debug(f"Processing event {event.id} (type={event.event_type})")

                    # Call handler with its own session
                    await handler(event_db, event)

                    # Mark as published
                    await OutboxRepository.mark_published(event_db, event)
                    await event_db.commit()

                    duration_ms = int((time.perf_counter() - event_start) * 1000)
                    logger.info(
                        f"Successfully processed event {event.id} (type={event.event_type}) in {duration_ms}ms"
                    )
                    successful_count += 1

                except Exception as exc:  # noqa: BLE001
                    # Rollback the session on error
                    await event_db.rollback()

                    # Mark for retry with a fresh query
                    await event_db.refresh(event)
                    await OutboxRepository.mark_retry(event_db, event, error_message=str(exc))
                    await event_db.commit()

                    duration_ms = int((time.perf_counter() - event_start) * 1000)
                    logger.exception(
                        f"Failed to process event {event.id} (type={event.event_type}) after {duration_ms}ms: {exc}"
                    )
                    failed_count += 1

    # Process all events concurrently with semaphore limiting concurrency
    await asyncio.gather(*[process_single_event(event) for event in events], return_exceptions=True)

    # Log summary
    total_duration_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info(
        f"Outbox batch processing completed in {total_duration_ms}ms: "
        f"{successful_count} successful, {failed_count} failed, {no_handler_count} no handler"
    )

    return events
