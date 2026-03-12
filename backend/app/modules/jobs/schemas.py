"""
Pydantic schemas for Job API requests and responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.shared.pagination import PaginatedResponse


class JobBase(BaseModel):
    """Base Job schema with essential fields for list display"""
    id: int
    source: Optional[str] = None
    source_id: str
    title: str
    abstract: Optional[str] = None

    # Salary
    salary_label: Optional[str] = None

    # Work type
    work_types_label: Optional[str] = None

    # Location
    location_label: Optional[str] = None
    location_city: Optional[str] = None
    country: Optional[str] = None

    # Company
    advertiser_name: Optional[str] = None
    company_name: Optional[str] = None
    company_logo: Optional[str] = None

    # Classification
    classification: Optional[str] = None
    sub_classification: Optional[str] = None

    # Dates
    listed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Status flags
    is_expired: Optional[bool] = False
    status: Optional[str] = None

    # Share link
    share_link: Optional[str] = None

    # User-specific metadata
    is_viewed: bool = False
    last_viewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class JobDetail(JobBase):
    """Detailed Job schema with full information"""
    content: Optional[str] = None
    content_cn: Optional[str] = Field(default=None, description="Job description translated to Chinese")

    # Contact info
    phone_number: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    # Work type details
    work_type_ids: Optional[str] = None

    # Location details
    location_area: Optional[str] = None
    location_ids: Optional[str] = None
    country_code: Optional[str] = None
    suburb: Optional[str] = None
    region: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    broader_location_name: Optional[str] = None

    # Advertiser details
    advertiser_id: Optional[str] = None
    advertiser_is_verified: Optional[bool] = False
    advertiser_registration_date: Optional[datetime] = None
    is_private_advertiser: Optional[bool] = False

    # Classification details
    classification_id: Optional[str] = None
    sub_classification_id: Optional[str] = None
    classifications_label: Optional[str] = None

    # Branding
    product_bullets: Optional[str] = None
    branding_id: Optional[str] = None
    branding_cover_url: Optional[str] = None
    branding_thumbnail_url: Optional[str] = None
    branding_logo_url: Optional[str] = None
    display_tags: Optional[str] = None

    # Company details
    company_profile_id: Optional[str] = None
    company_slug: Optional[str] = None
    company_description: Optional[str] = None
    company_industry: Optional[str] = None
    company_size: Optional[str] = None
    company_website: Optional[str] = None
    should_display_reviews: Optional[bool] = False

    # Normalized fields
    normalised_role_title: Optional[str] = None
    normalised_organisation_name: Optional[str] = None

    # Other metadata
    source_zone: Optional[str] = None
    ad_product_type: Optional[str] = None
    has_role_requirements: Optional[bool] = False
    restricted_application_label: Optional[str] = None

    # Verification flags
    is_link_out: Optional[bool] = False
    is_verified: Optional[bool] = False

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Analysis
    analysis: Optional["JobAnalysisResponse"] = None


class JobListResponse(PaginatedResponse[JobBase]):
    """Paginated job list response"""


class SavedJobStatus(BaseModel):
    """Saved status for a user-job pair."""

    is_saved: bool
    saved_at: Optional[datetime] = None


class JobViewedStatus(BaseModel):
    """Viewed status for a user-job pair."""

    is_viewed: bool
    first_viewed_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None
    view_count: int = 0


class SavedJobItem(BaseModel):
    """Saved jobs list item."""

    job: JobBase
    saved_at: datetime


class SavedJobListResponse(PaginatedResponse[SavedJobItem]):
    """Paginated saved jobs response."""


class JobFiltersRequest(BaseModel):
    """Job filtering parameters"""
    # Search
    keyword: Optional[str] = Field(None, description="Search keyword for title and description")

    # Filters
    location_cities: Optional[list[str]] = Field(None, description="Filter by location cities")
    work_types: Optional[list[str]] = Field(None, description="Filter by work types")
    companies: Optional[list[str]] = Field(None, description="Filter by company names")
    sources: Optional[list[str]] = Field(None, description="Filter by job sources")
    view_status: str = Field("all", description="Viewed status filter: all, viewed, unviewed")

    # Date range
    listed_after: Optional[datetime] = Field(None, description="Filter jobs listed after this date")
    listed_before: Optional[datetime] = Field(None, description="Filter jobs listed before this date")

    # Sorting
    sort_by: str = Field("listed_at", description="Sort field")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


class JobFiltersOptions(BaseModel):
    """Available filter options (for filter dropdowns)"""
    location_cities: list[str] = Field(default_factory=list, description="Available location cities")
    work_types: list[str] = Field(default_factory=list, description="Available work types")
    companies: list[str] = Field(default_factory=list, description="Available companies")
    sources: list[str] = Field(default_factory=list, description="Available job sources")


# ============================================
# Job Analysis Schemas
# ============================================

class JobAnalysisBase(BaseModel):
    """Job analysis output schema"""

    # Skills Requirements
    required_skills: list[str] = Field(default_factory=list, description="Must-have technical skills")
    preferred_skills: list[str] = Field(default_factory=list, description="Nice-to-have skills")
    certifications: list[str] = Field(default_factory=list, description="Required or preferred certifications")
    tech_stack: list[str] = Field(default_factory=list, description="Technologies, frameworks, and tools")

    # Responsibilities & Requirements
    seniority: Optional[str] = Field(None, description="Seniority level (Junior, Mid, Senior, Lead)")
    key_responsibilities: list[str] = Field(default_factory=list, description="Main job responsibilities")
    experience_years: Optional[str] = Field(None, description="Required experience (e.g., '3-5 years')")
    education_requirement: Optional[str] = Field(None, description="Education requirement")

    # Soft Requirements
    soft_skills: list[str] = Field(default_factory=list, description="Soft skills")
    company_culture_keywords: list[str] = Field(default_factory=list, description="Company culture descriptors")

    # Agent Inference
    hiring_priorities: list[str] = Field(default_factory=list, description="Agent's inference: top hiring priorities")

    # Translations
    cn_content: Optional[str] = Field(default=None, description="Job description translated to Chinese")


class JobAnalysisResponse(JobAnalysisBase):
    """API response for job analysis"""

    id: str
    job_id: int
    analysis_version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobAnalysisCreate(JobAnalysisBase):
    """Schema for creating job analysis (internal use)"""

    job_id: int
    analysis_version: str = "v1.0.0"


# ============================================
# Matching Schemas
# ============================================


class JobBriefInfo(BaseModel):
    """Minimal job info for match list."""

    id: int
    source: Optional[str]
    title: str
    advertiser_name: Optional[str]
    location_label: Optional[str]
    work_types_label: Optional[str]
    salary_label: Optional[str]
    listed_at: Optional[datetime]

    # Additional fields for UI completeness
    company_logo: Optional[str] = None
    abstract: Optional[str] = None
    classification: Optional[str] = None
    sub_classification: Optional[str] = None
    is_viewed: bool = False
    last_viewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ResumeBriefInfo(BaseModel):
    """Minimal resume info for matches."""

    id: str
    title: str

    model_config = {"from_attributes": True}


class UserJobMatchResponse(BaseModel):
    """Match list item for current user."""

    id: str
    job: JobBriefInfo
    skill_match_score: float = Field(..., description="Skill match score (0-100)")
    resume_match_score: Optional[float] = Field(None, description="Resume match score (0-100)")
    ai_match_score: Optional[float] = Field(None, description="AI match score (0-100)")
    recommended_resume: Optional[ResumeBriefInfo]
    skill_match_details: dict
    ai_analysis: Optional[dict] = None
    calculated_at: datetime
    ai_analyzed_at: Optional[datetime]


class UserJobMatchDetailResponse(BaseModel):
    """Detailed match info for current user on a job."""

    id: str
    job: JobDetail  # full job
    job_analysis: JobAnalysisResponse
    skill_match_score: float
    skill_match_details: dict
    resume_match_score: Optional[float]
    resume_match_details: Optional[dict]
    recommended_resume: Optional[ResumeBriefInfo]
    ai_match_score: Optional[float]
    ai_analysis: Optional[dict]
    calculated_at: datetime
    ai_analyzed_at: Optional[datetime]
