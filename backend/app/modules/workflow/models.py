"""Workflow execution models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Integer,
    Float,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import TaskStatus, AICallStatus


def _uuid() -> str:
    """Generate UUID4 string for primary keys."""
    return str(uuid4())


class TaskExecution(Base, TimestampMixin):
    """Individual task execution record."""

    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, native_enum=False),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True)
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    execution_time_ms: Mapped[Optional[int]
                              ] = mapped_column(Integer, nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    depends_on: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_task_executions_entity', 'entity_type', 'entity_id'),
    )


class AICall(Base, TimestampMixin):
    """AI call tracking (cost/latency)."""

    __tablename__ = "ai_calls"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    workflow_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    task_id: Mapped[Optional[str]] = mapped_column(ForeignKey(
        "task_executions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    agent_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Optional[float]
                           ] = mapped_column(Float, nullable=True)
    status: Mapped[AICallStatus] = mapped_column(
        SQLEnum(AICallStatus, native_enum=False),
        nullable=False,
        default=AICallStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True)

    task: Mapped[Optional["TaskExecution"]] = relationship("TaskExecution")
