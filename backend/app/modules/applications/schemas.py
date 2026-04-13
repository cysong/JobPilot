"""Pydantic schemas for applications module."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.shared.enums import ApplicationResolution, ApplicationStatus, TailoringLevel
from app.shared.pagination import PaginatedResponse


class ApplicationCreateRequest(BaseModel):
    """Request payload for creating an application."""

    job_id: int = Field(..., description="Job ID to apply for")
    resume_template_id: str = Field(..., description="Resume template ID selected by user")
    tailoring_level: TailoringLevel = Field(
        default=TailoringLevel.LIGHT,
        description="Tailoring level (resume-focused)",
    )


class ApplicationRetryRequest(BaseModel):
    """Request payload for retrying generation with optional new inputs."""

    resume_template_id: Optional[str] = Field(
        default=None, description="Optional resume template ID to use for retry"
    )
    tailoring_level: Optional[TailoringLevel] = Field(
        default=None, description="Optional tailoring level override for retry"
    )


class ApplicationStatusUpdateRequest(BaseModel):
    """Request payload for updating application status manually."""

    status: ApplicationStatus = Field(..., description="Target application status")
    note: Optional[str] = Field(
        default=None,
        description="Optional note for status change history",
        max_length=500,
    )


class ApplicationResolutionUpdateRequest(BaseModel):
    """Request payload for updating application resolution manually."""

    resolution: ApplicationResolution = Field(..., description="Target application resolution")
    note: Optional[str] = Field(
        default=None,
        description="Optional note for resolution change history",
        max_length=500,
    )


class ApplicationJobInfo(BaseModel):
    """Job fields exposed within application responses."""

    id: int
    title: str
    source: Optional[str] = None
    advertiser_name: Optional[str] = None
    company_name: Optional[str] = None
    company_logo: Optional[str] = None
    location_label: Optional[str] = None
    work_types_label: Optional[str] = None
    salary_label: Optional[str] = None
    classification: Optional[str] = None
    sub_classification: Optional[str] = None
    share_link: Optional[str] = None
    listed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationCompanyRoleItem(BaseModel):
    """Same-company application item shown on application detail page."""

    id: str
    job_id: int
    status: ApplicationStatus
    resolution: ApplicationResolution
    updated_at: datetime
    job: ApplicationJobInfo

    model_config = ConfigDict(from_attributes=True)


class ApplicationResponse(BaseModel):
    """Base response for application resources."""

    id: str
    job_id: int
    source_resume_id: str
    resume_document_id: Optional[str] = None
    cover_letter_document_id: Optional[str] = None
    status: ApplicationStatus
    resolution: ApplicationResolution
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    applied_at: Optional[datetime] = None
    offered_at: Optional[datetime] = None
    tailoring_level: TailoringLevel
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    job: Optional[ApplicationJobInfo] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationDetail(ApplicationResponse):
    """Detailed response (currently same as base, reserved for extension)."""
    pass


class ApplicationListResponse(PaginatedResponse[ApplicationDetail]):
    """Paginated list response for applications."""


class ApplicationCompanyRoleListResponse(BaseModel):
    """Response for same-company related applications."""

    items: list[ApplicationCompanyRoleItem]
