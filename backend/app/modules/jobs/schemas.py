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

    model_config = {"from_attributes": True}


class JobDetail(JobBase):
    """Detailed Job schema with full information"""
    content: Optional[str] = None

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


class JobListResponse(PaginatedResponse[JobBase]):
    """Paginated job list response"""


class JobFiltersRequest(BaseModel):
    """Job filtering parameters"""
    # Search
    keyword: Optional[str] = Field(None, description="Search keyword for title and description")

    # Filters
    location_cities: Optional[list[str]] = Field(None, description="Filter by location cities")
    work_types: Optional[list[str]] = Field(None, description="Filter by work types")
    companies: Optional[list[str]] = Field(None, description="Filter by company names")

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
