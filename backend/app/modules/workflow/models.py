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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import WorkflowStatus, TaskStatus, AICallStatus


def _uuid() -> str:
    """Generate UUID4 string for primary keys."""
    return str(uuid4())


class WorkflowExecution(Base, TimestampMixin):
    """Workflow execution record."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    workflow_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1.0.0")
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_id: Mapped[str] = mapped_column(
        String(255), nullable=True, index=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        SQLEnum(WorkflowStatus, native_enum=False),
        nullable=False,
        default=WorkflowStatus.PENDING,
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True)
    input_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)

    # Relationships
    tasks: Mapped[list["TaskExecution"]] = relationship(
        "TaskExecution", back_populates="workflow", cascade="all, delete-orphan")
    ai_calls: Mapped[list["AICall"]] = relationship(
        "AICall", back_populates="workflow", cascade="all, delete-orphan")


class TaskExecution(Base, TimestampMixin):
    """Individual task execution record."""

    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(ForeignKey(
        "workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, native_enum=False),
        nullable=False,
        default=TaskStatus.PENDING,
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
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True)
    depends_on: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)

    workflow: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution", back_populates="tasks")


class AICall(Base, TimestampMixin):
    """AI call tracking (cost/latency)."""

    __tablename__ = "ai_calls"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_uuid)
    workflow_id: Mapped[Optional[str]] = mapped_column(ForeignKey(
        "workflow_executions.id", ondelete="SET NULL"), nullable=True, index=True)
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

    workflow: Mapped[Optional["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="ai_calls")
    task: Mapped[Optional["TaskExecution"]] = relationship("TaskExecution")
