"""Models for job applications."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import ApplicationResolution, ApplicationStatus, TailoringLevel

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.resumes.models import Document, Resume


def _uuid() -> str:
    """Generate UUID4 string for primary keys."""
    return str(uuid4())


class ApplicationStatusHistory(Base):
    """Records each status transition for an application."""

    __tablename__ = "application_status_history"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(
        "Application", back_populates="status_history"
    )


class OutboxEvent(Base, TimestampMixin):
    """Outbox event for reliable publish."""

    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Application(Base, TimestampMixin):
    """Job application with resume/cover letter generation pipeline."""

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
    )

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey(
        "seek_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_resume_id: Mapped[str] = mapped_column(
        ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=False)
    resume_document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    cover_letter_document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(ApplicationStatus, native_enum=False),
        default=ApplicationStatus.PENDING,
        nullable=False,
        index=True,
    )
    resolution: Mapped[ApplicationResolution] = mapped_column(
        SQLEnum(ApplicationResolution, native_enum=False),
        default=ApplicationResolution.ACTIVE,
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    offered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    tailoring_level: Mapped[TailoringLevel] = mapped_column(
        SQLEnum(
            TailoringLevel,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            validate_strings=True,
        ),
        default=TailoringLevel.LIGHT,
        nullable=False,
    )
    tailoring_progress: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    job: Mapped["SeekJob"] = relationship("SeekJob")
    source_resume: Mapped["Resume"] = relationship(
        "Resume", foreign_keys=[source_resume_id])
    resume_document: Mapped[Optional["Document"]] = relationship(
        "Document", foreign_keys=[resume_document_id])
    cover_letter_document: Mapped[Optional["Document"]] = relationship(
        "Document", foreign_keys=[cover_letter_document_id])
    status_history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        "ApplicationStatusHistory",
        back_populates="application",
        order_by="ApplicationStatusHistory.changed_at.desc()",
        lazy="noload",
    )

    def mark_failed(self, error: str):
        """Helper to mark application failed with error message."""
        self.status = ApplicationStatus.FAILED
        self.last_error = error
