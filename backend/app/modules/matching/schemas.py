"""API schemas for matching v3 results, role families and admin tools."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.modules.jobs.schemas import JobBriefInfo, ResumeBriefInfo

Tier = Literal["A", "B", "C", "D"]
MatchView = Literal["recommended", "rejected"]


class MatchLabelInfo(BaseModel):
    """The admin's current label for a pair (admins only)."""

    id: str
    label: str
    reason_tags: list[str]
    note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchSummary(BaseModel):
    """Match result fields shown on a job card."""

    id: str
    status: str
    tier: Optional[Tier]
    tier_reason: Optional[str]
    tech_level: Optional[str]
    experience_level: Optional[str]
    family_relation: str
    location_check: str
    reject_code: Optional[str]
    reject_reason: Optional[str]
    reject_quote: Optional[str]
    judged_at: Optional[datetime]
    recommended_resume: Optional[ResumeBriefInfo]
    application_status: Optional[str] = None
    label: Optional[MatchLabelInfo] = None


class MatchListItem(BaseModel):
    job: JobBriefInfo
    match: MatchSummary


class MatchCounts(BaseModel):
    A: int = 0
    B: int = 0
    C: int = 0
    rejected: int = 0
    pending: int = 0  # queued or waiting for a retry


class MatchListResponse(BaseModel):
    items: list[MatchListItem]
    total: int
    counts: MatchCounts


class MatchDetail(MatchSummary):
    """Full judgment for the job detail page."""

    job_id: int
    tech_items: list[dict[str, Any]] = Field(default_factory=list)
    relevant_years: Optional[float] = None
    required_years: Optional[float] = None
    experience_evidence: list[dict[str, Any]] = Field(default_factory=list)
    work_rights: Optional[dict[str, Any]] = None
    security_clearance: Optional[dict[str, Any]] = None
    work_location: Optional[dict[str, Any]] = None
    languages: Optional[dict[str, Any]] = None
    other_constraints: list[dict[str, Any]] = Field(default_factory=list)
    seniority_mismatch: Optional[bool] = None
    is_different_track: Optional[bool] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None


class RoleFamilyInfo(BaseModel):
    key: str
    label: str
    label_zh: str
    description: str


class ResumeRoleFamilyUpdate(BaseModel):
    role_family: Optional[str] = Field(None, description="Family key, or null to exclude the resume from matching")


class ResumeRoleFamilyResponse(BaseModel):
    resume_id: str
    role_family: Optional[str]
    role_family_source: Optional[str]


class MatchLabelCreate(BaseModel):
    job_id: int
    label: Literal["A", "B", "C", "D", "REJECT"]
    reason_tags: list[str] = Field(default_factory=list)
    note: Optional[str] = Field(None, max_length=2000)


MAX_LABEL_BATCH = 200


class MatchLabelBatchCreate(BaseModel):
    labels: list[MatchLabelCreate] = Field(..., min_length=1, max_length=MAX_LABEL_BATCH)


class MatchLabelBatchError(BaseModel):
    index: int
    job_id: int
    error: str


class MatchLabelBatchResponse(BaseModel):
    """Valid items are saved even when others fail; ``errors`` lists the rest by index."""

    created: list[MatchLabelInfo]
    errors: list[MatchLabelBatchError]


class TitleFamilyItem(BaseModel):
    title_key: str
    example_title: str
    status: str
    role_family: Optional[str]
    source: str
    families_version: str
    job_count: int = 0
    updated_at: datetime


class TitleFamilyListResponse(BaseModel):
    items: list[TitleFamilyItem]
    total: int


class TitleFamilyUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="A job title or an existing title key")
    role_family: Optional[str] = Field(None, description="Family key, or null for ambiguous (read the JD)")


class TitleFamilyUpdateResponse(BaseModel):
    item: TitleFamilyItem
    jobs_changed: int
    jobs_to_pending: int
