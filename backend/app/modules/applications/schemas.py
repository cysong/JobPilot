"""Pydantic schemas for applications module."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.shared.enums import ApplicationStatus


class ApplicationCreateRequest(BaseModel):
    """Request payload for creating an application."""

    job_id: int = Field(..., description="Job ID to apply for")
    resume_template_id: str = Field(..., description="Resume template ID selected by user")
    tailoring_level: str = Field(default="light", description="Tailoring level (resume-focused)")


class ApplicationResponse(BaseModel):
    """Base response for application resources."""

    id: str
    job_id: int
    source_resume_id: str
    resume_document_id: Optional[str] = None
    cover_letter_document_id: Optional[str] = None
    status: ApplicationStatus
    tailoring_level: str
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationDetail(ApplicationResponse):
    """Detailed response (currently same as base, reserved for extension)."""
    pass
