"""
Job models for read-only access to seek_jobs table.
This table is maintained by external crawler system.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref

from app.shared.base_model import Base, TimestampMixin


def _uuid() -> str:
    """Generate UUID4 string for primary keys."""
    return str(uuid4())


class SeekJob(Base):
    """
    Read-only model for seek_jobs table (maintained by external crawler).

    JobPilot system only reads from this table, never writes.
    """
    __tablename__ = "seek_jobs"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_seek_jobs_source_source_id"),
    )

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)

    # Core fields
    source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True)
    source_id: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True)

    # Boolean flags
    is_expired: Mapped[Optional[bool]] = mapped_column(
        Boolean, default=False, index=True)
    is_link_out: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    is_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Contact info
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True)
    share_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dates
    listed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)

    # Salary
    salary_label: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True)

    # Work type
    work_types_label: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    work_type_ids: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True)

    # Location
    location_label: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True)
    location_area: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True)
    location_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    suburb: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Advertiser info
    advertiser_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True)
    advertiser_name: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True, index=True)
    advertiser_is_verified: Mapped[Optional[bool]
                                   ] = mapped_column(Boolean, default=False)
    advertiser_registration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    is_private_advertiser: Mapped[Optional[bool]
                                  ] = mapped_column(Boolean, default=False)

    # Classification
    classification_id: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True)
    classification: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True)
    sub_classification_id: Mapped[Optional[str]
                                  ] = mapped_column(String(20), nullable=True)
    sub_classification: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True)
    classifications_label: Mapped[Optional[str]
                                  ] = mapped_column(String(500), nullable=True)

    # Branding
    product_bullets: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    branding_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    branding_cover_url: Mapped[Optional[str]
                               ] = mapped_column(Text, nullable=True)
    branding_thumbnail_url: Mapped[Optional[str]
                                   ] = mapped_column(Text, nullable=True)
    branding_logo_url: Mapped[Optional[str]
                              ] = mapped_column(Text, nullable=True)
    display_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Company info
    company_profile_id: Mapped[Optional[str]
                               ] = mapped_column(String(50), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True)
    company_slug: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True)
    company_logo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_description: Mapped[Optional[str]
                                ] = mapped_column(Text, nullable=True)
    company_industry: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    should_display_reviews: Mapped[Optional[bool]
                                   ] = mapped_column(Boolean, default=False)

    # Normalized fields
    normalised_role_title: Mapped[Optional[str]
                                  ] = mapped_column(String(300), nullable=True)
    normalised_organisation_name: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True)
    broader_location_name: Mapped[Optional[str]
                                  ] = mapped_column(String(100), nullable=True)

    # Other metadata
    source_zone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True)
    ad_product_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True)
    has_role_requirements: Mapped[Optional[bool]
                                  ] = mapped_column(Boolean, default=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    restricted_application_label: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)


class JobAnalysis(Base, TimestampMixin):
    """
    AI-generated job analysis results.

    Only successful analyses are stored here.
    Failed attempts are tracked via TaskExecution.
    """
    __tablename__ = "job_analyses"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid
    )

    # Foreign key to job (unique: one analysis per job)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("seek_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to analyzed job"
    )

    # ============================================
    # Job Title Normalization
    # ============================================
    normalized_job_title: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        index=True,
        comment="Standardized job title (e.g., 'Backend Developer')"
    )

    # ============================================
    # Skills Requirements
    # ============================================
    required_skills: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Must-have technical skills"
    )
    preferred_skills: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Nice-to-have skills"
    )
    certifications: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Required or preferred certifications"
    )
    tech_stack: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Technologies, frameworks, and tools"
    )

    # ============================================
    # Responsibilities & Requirements
    # ============================================
    seniority: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Seniority level (Junior, Intermediate, Senior, Lead)"
    )
    key_responsibilities: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Main job responsibilities (3-5 key points)"
    )
    experience_years: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Required experience (e.g., '3-5 years', '5+ years')"
    )
    education_requirement: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Education requirement"
    )

    # ============================================
    # Soft Requirements
    # ============================================
    soft_skills: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Soft skills (teamwork, communication, etc.)"
    )
    company_culture_keywords: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Company culture descriptors"
    )
    cn_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Translated job description in Chinese"
    )

    # ============================================
    # Agent Inference
    # ============================================
    hiring_priorities: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Agent's inference: what does company value most? (top 3)"
    )

    # ============================================
    # Metadata
    # ============================================
    analysis_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1.0.0",
        comment="Analysis schema version for future compatibility"
    )
    needs_reanalysis: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Flag to trigger re-analysis"
    )

    # ============================================
    # Relationships
    # ============================================
    job: Mapped["SeekJob"] = relationship("SeekJob", backref=backref("analysis", uselist=False))


class UserSavedJob(Base, TimestampMixin):
    """Saved jobs per user."""

    __tablename__ = "user_saved_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_saved_jobs_user_job"),
    )

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("seek_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship("User")
    job: Mapped["SeekJob"] = relationship("SeekJob")
