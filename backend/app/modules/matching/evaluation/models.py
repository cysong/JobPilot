"""ORM models for matching evaluation (docs/job_matching_v3_design.md §9.7)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base


class ItemKind:
    INTERVIEWED = "interviewed"
    APPLIED = "applied"
    RANDOM = "random"
    RANDOM_FILTERED = "random_filtered"
    LABELED = "labeled"


class MatchEvalDataset(Base):
    __tablename__ = "match_eval_datasets"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_match_eval_datasets_name_version"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class MatchEvalItem(Base):
    __tablename__ = "match_eval_items"

    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("match_eval_datasets.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    applied_resume_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class MatchEvalRun(Base):
    __tablename__ = "match_eval_runs"
    __table_args__ = (
        Index("ix_match_eval_runs_dataset_started", "dataset_id", text("started_at DESC")),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("match_eval_datasets.id"), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    baseline_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("match_eval_runs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    report_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchEvalPrediction(Base):
    __tablename__ = "match_eval_predictions"

    run_id: Mapped[str] = mapped_column(ForeignKey("match_eval_runs.id", ondelete="CASCADE"), primary_key=True)
    repeat_index: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default="0")
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prefilter: Mapped[str] = mapped_column(String(20), nullable=False)
    location_check: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    reject_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    resume_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    judgment: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
