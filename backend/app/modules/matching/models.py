"""User-job matching persistence models.

``UserJobMatch`` is the v1 table (DEPRECATED, kept read-only for history).
``JobMatch`` is the v3 result and judge queue (docs/job_matching_v3_design.md §9.5).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin


class UserJobMatch(Base, TimestampMixin):
    """Match result between a user and a job.

    DEPRECATED v1 — read-only archive; v3 writes ``JobMatch``.
    """

    __tablename__ = "user_job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_match"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("seek_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    skill_match_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_match_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    recommended_resume_id: Mapped[Optional[str]] = mapped_column(
        String(255), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    resume_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resume_match_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    ai_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    matching_algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0.0")

    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ai_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    recommended_resume: Mapped["Resume"] = relationship("Resume", foreign_keys=[recommended_resume_id])
    job: Mapped["SeekJob"] = relationship("SeekJob", foreign_keys=[job_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class JobMatchStatus:
    QUEUED = "queued"
    RATED = "rated"
    REJECTED = "rejected"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    SKIPPED_EXPIRED = "skipped_expired"

    ALL = (QUEUED, RATED, REJECTED, FAILED_RETRYABLE, FAILED_FINAL, SKIPPED_EXPIRED)


class RejectCode:
    LOCATION = "LOCATION"
    WORK_RIGHTS = "WORK_RIGHTS"
    SECURITY_CLEARANCE = "SECURITY_CLEARANCE"


class JobMatch(Base, TimestampMixin):
    """One row per job x user: the v3 judgment, and the judge queue entry."""

    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
        CheckConstraint(
            "status IN ('queued','rated','rejected','failed_retryable','failed_final','skipped_expired')",
            name="ck_job_matches_status",
        ),
        CheckConstraint("tier IS NULL OR tier IN ('A','B','C','D')", name="ck_job_matches_tier"),
        CheckConstraint(
            "status <> 'rated' OR (tier IS NOT NULL AND resume_id IS NOT NULL)",
            name="ck_job_matches_rated",
        ),
        CheckConstraint("status <> 'rejected' OR reject_code IS NOT NULL", name="ck_job_matches_rejected"),
        CheckConstraint(
            "reject_code IS DISTINCT FROM 'LOCATION' OR (ai_call_id IS NULL AND location_check = 'rejected')",
            name="ck_job_matches_location_reject",
        ),
        Index("ix_job_matches_listing", "user_id", "status", "tier"),
        Index(
            "ix_job_matches_queue",
            text("job_listed_at DESC"),
            postgresql_where=text("status = 'queued'"),
        ),
        Index(
            "ix_job_matches_retry",
            "next_attempt_at",
            postgresql_where=text("status = 'failed_retryable'"),
        ),
        Index("ix_job_matches_job", "job_id"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("seek_jobs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, comment="new_job | backfill")
    job_family: Mapped[str] = mapped_column(String(32), nullable=False)
    families_version: Mapped[str] = mapped_column(String(16), nullable=False)
    family_relation: Mapped[str] = mapped_column(String(8), nullable=False, comment="same | adjacent")
    candidate_resume_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    location_check: Mapped[str] = mapped_column(String(16), nullable=False)
    job_listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    job_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Resumes are soft-deleted, so the FK does not cascade.
    resume_id: Mapped[Optional[str]] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    resume_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    tier_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tech_level: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    experience_level: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    reject_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reject_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    judgment: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    validation: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ai_call_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    judged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
