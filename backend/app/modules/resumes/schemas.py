"""
Pydantic schemas for Resume API requests and responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.modules.resumes.models import DocumentFormat


# ============================================
# Document Schemas
# ============================================

class DocumentBase(BaseModel):
    """Base Document schema"""
    id: str
    root_id: str
    parent_id: Optional[str] = None
    format: DocumentFormat
    content: str
    content_hash: str
    change_comments: Optional[str] = None
    extra_metadata: Optional[dict] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentVersion(BaseModel):
    """Document version info (lightweight, without full content)"""
    id: str
    root_id: str
    parent_id: Optional[str] = None
    format: DocumentFormat
    content_hash: str
    change_comments: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Resume Schemas
# ============================================

class ResumeBase(BaseModel):
    """Base Resume schema"""
    title: str = Field(..., min_length=1, max_length=200, description="Resume title")


class ResumeCreate(ResumeBase):
    """Schema for creating a new resume"""
    content: str = Field(..., min_length=1, description="Resume content in Markdown")
    format: DocumentFormat = Field(default=DocumentFormat.MARKDOWN, description="Document format")


class ResumeUpdate(BaseModel):
    """Schema for updating resume content"""
    content: str = Field(..., min_length=1, description="Updated resume content")
    change_comments: Optional[str] = Field(None, description="Description of changes made")


class ResumeTitleUpdate(BaseModel):
    """Schema for updating resume title"""
    title: str = Field(..., min_length=1, max_length=200, description="New resume title")


class ResumeResponse(ResumeBase):
    """Resume response with full details"""
    id: str
    user_id: int
    document_id: str
    is_draft: bool
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Embedded document content
    document: DocumentBase

    model_config = {"from_attributes": True}


class ResumeListItem(ResumeBase):
    """Resume list item (without full document content)"""
    id: str
    user_id: int
    is_draft: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    # Only include metadata, not full content
    content_preview: Optional[str] = Field(None, description="First 200 characters of content")

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    """Paginated resume list response"""
    items: list[ResumeListItem]
    total: int
    draft_count: int
    formal_count: int


class FormalResumeLimit(BaseModel):
    """Formal resume limit check response"""
    limit: int
    current_count: int
    can_create_more: bool
    remaining: int
