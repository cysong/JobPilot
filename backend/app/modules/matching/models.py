"""User-job matching persistence model."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin


class UserJobMatch(Base, TimestampMixin):
    """Match result between a user and a job."""

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
