"""
Shared Pydantic schemas for unified document editing flows.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.modules.resumes.models import DocumentFormat


class DocumentEditResponse(BaseModel):
    """
    Unified response for document editing across business contexts.

    business_type indicates which domain owns the document (resume/tailored_resume/cover_letter).
    """

    # Business metadata
    business_type: Literal["resume", "tailored_resume", "cover_letter"]
    business_id: str  # resume_id or application_id
    title: str

    # Document data
    document_id: str
    content: str
    format: DocumentFormat

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Optional context for tailored documents
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    source_resume_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdateRequest(BaseModel):
    """Request payload for updating document content."""

    content: str
    change_comments: Optional[str] = None
