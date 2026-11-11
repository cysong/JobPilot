"""ORM models for role family classification (docs/job_matching_v3_design.md §9.2-9.3)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin


class TitleFamilyStatus:
    CLASSIFIED = "classified"
    AMBIGUOUS = "ambiguous"


class TitleFamilySource:
    LLM = "llm"
    ADMIN = "admin"


class JobFamilyStatus:
    PENDING = "pending"
    CLASSIFIED = "classified"
    FAILED = "failed"


class JobFamilyMethod:
    TITLE_CACHE = "title_cache"
    JD_READ = "jd_read"


class JobTitleFamily(Base, TimestampMixin):
    """Cache: normalized job title -> role family (or ambiguous)."""

    __tablename__ = "job_title_families"
    __table_args__ = (
        CheckConstraint("status IN ('classified','ambiguous')", name="ck_job_title_families_status"),
        CheckConstraint(
            "status <> 'classified' OR role_family IS NOT NULL", name="ck_job_title_families_family"
        ),
        Index("ix_job_title_families_family", "role_family"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    example_title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    role_family: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    families_version: Mapped[str] = mapped_column(String(16), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class JobRoleFamily(Base, TimestampMixin):
    """Final role family per job, used directly by the prefilter."""

    __tablename__ = "job_role_families"
    __table_args__ = (
        CheckConstraint("status IN ('pending','classified','failed')", name="ck_job_role_families_status"),
        Index(
            "ix_job_role_families_family",
            "role_family",
            postgresql_where=text("status = 'classified'"),
        ),
        Index("ix_job_role_families_title_key", "title_key"),
        Index("ix_job_role_families_duplicate_of", "duplicate_of",
              postgresql_where=text("duplicate_of IS NOT NULL")),
        Index(
            "ix_job_role_families_pending",
            "status",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("seek_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    title_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=JobFamilyStatus.PENDING)
    role_family: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    families_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_call_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # First listing of the same job in another city / on another platform (matching.duplicates).
    duplicate_of: Mapped[Optional[int]] = mapped_column(
        ForeignKey("seek_jobs.id", ondelete="SET NULL"), nullable=True
    )
