"""Application workflow related event definitions."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ApplicationEventType(str, Enum):
    """Outbox event types for application workflows."""

    APPLICATION_CREATED = "application_created"
    APPLICATION_READY = "application_ready"
    APPLICATION_FAILED = "application_failed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


class ApplicationCreatedPayload(BaseModel):
    """Payload for application_created events."""

    application_id: str
    user_id: int
    job_id: int
    resume_document_id: str
    tailoring_level: Optional[str] = Field(default=None)
    is_retry: bool = False


class ApplicationReadyPayload(BaseModel):
    """Payload when application artifacts are ready."""

    application_id: str
    cover_letter_document_id: Optional[str] = None
    resume_document_id: Optional[str] = None
    status: str


class ApplicationFailedPayload(BaseModel):
    """Payload when application pipeline fails."""

    application_id: str
    error: str


EventPayload = ApplicationCreatedPayload | ApplicationReadyPayload | ApplicationFailedPayload
