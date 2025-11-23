"""
Job models for read-only access to seek_jobs table.
This table is maintained by external crawler system.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base


class SeekJob(Base):
    """
    Read-only model for seek_jobs table (maintained by external crawler).

    JobPilot system only reads from this table, never writes.
    """
    __tablename__ = "seek_jobs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core fields
    source_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Boolean flags
    is_expired: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, index=True)
    is_link_out: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    is_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Contact info
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    share_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dates
    listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Salary
    salary_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Work type
    work_types_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    work_type_ids: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Location
    location_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    location_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    suburb: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Advertiser info
    advertiser_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    advertiser_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True, index=True)
    advertiser_is_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    advertiser_registration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_private_advertiser: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Classification
    classification_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    classification: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    sub_classification_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sub_classification: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    classifications_label: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Branding
    product_bullets: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    branding_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    branding_cover_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    branding_thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    branding_logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Company info
    company_profile_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    company_slug: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_logo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    should_display_reviews: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Normalized fields
    normalised_role_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    normalised_organisation_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    broader_location_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Other metadata
    source_zone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ad_product_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    has_role_requirements: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    restricted_application_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
