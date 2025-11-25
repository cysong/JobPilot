"""Outbox event handlers for application workflows."""
from __future__ import annotations

import logging
from typing import Callable, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.event_types import (
    ApplicationCreatedPayload,
    ApplicationEventType,
)
from app.modules.applications.models import OutboxEvent
from app.modules.applications.workflow_service import WorkflowService

logger = logging.getLogger(__name__)


async def handle_application_created(db: AsyncSession, event: OutboxEvent) -> None:
    """
    Handle application_created event by initializing workflow.

    Args:
        db: Database session (dedicated to this event)
        event: Outbox event containing ApplicationCreatedPayload

    Raises:
        ValidationError: If payload is invalid
        Exception: If workflow initialization fails
    """
    try:
        payload = ApplicationCreatedPayload(**event.payload)

        logger.info(
            f"Handling application_created event for application_id={payload.application_id}, "
            f"user_id={payload.user_id}, is_retry={payload.is_retry}"
        )

        await WorkflowService.init_workflow_for_application(db, payload)

        logger.debug(
            f"Successfully initialized workflow for application_id={payload.application_id}"
        )

    except Exception as exc:
        logger.error(
            f"Failed to handle application_created event (event_id={event.id}): {exc}",
            exc_info=True
        )
        raise


HANDLERS: Dict[str, Callable[[AsyncSession, OutboxEvent], None]] = {
    ApplicationEventType.APPLICATION_CREATED.value: handle_application_created,
}
