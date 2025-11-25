"""Outbox event handlers for application workflows."""
from __future__ import annotations

from typing import Callable, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.event_types import (
    ApplicationCreatedPayload,
    ApplicationEventType,
)
from app.modules.applications.models import OutboxEvent
from app.modules.applications.workflow_service import WorkflowService


async def handle_application_created(db: AsyncSession, event: OutboxEvent) -> None:
    payload = ApplicationCreatedPayload(**event.payload)
    await WorkflowService.init_workflow_for_application(db, payload)


HANDLERS: Dict[str, Callable[[AsyncSession, OutboxEvent], None]] = {
    ApplicationEventType.APPLICATION_CREATED.value: handle_application_created,
}
