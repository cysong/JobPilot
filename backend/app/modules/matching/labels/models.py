"""ORM model for admin match labels (docs/job_matching_v3_design.md §9.6).

Append-only: relabeling a pair inserts a new row and points the previous one at
it through ``superseded_by``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base

LABEL_VALUES = ("A", "B", "C", "D", "REJECT")
REASON_TAGS = ("FAMILY", "TECH", "EXPERIENCE", "SENIORITY", "CONSTRAINT", "LOCATION", "OTHER")


class MatchLabel(Base):
    __tablename__ = "match_labels"
    __table_args__ = (
        CheckConstraint("label IN ('A','B','C','D','REJECT')", name="ck_match_labels_label"),
        Index(
            "ix_match_labels_current",
            "user_id",
            "job_id",
            postgresql_where=text("superseded_by IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("seek_jobs.id", ondelete="CASCADE"), nullable=False)
    job_match_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, comment="ui | import")
    labeled_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    predicted_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    predicted_tier: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    predicted_prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    predicted_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    predicted_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    superseded_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("match_labels.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
