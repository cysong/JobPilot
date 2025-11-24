"""Add application workflow tables

Revision ID: a1b2c3d4e5f6
Revises: 2b8ba0e2d92a
Create Date: 2025-11-24 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2b8ba0e2d92a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum-like check constraints (non-native enum)
    workflow_status_enum = sa.Enum(
        "Pending", "Running", "Completed", "Failed", "Cancelled",
        name="workflowstatus", native_enum=False
    )
    task_status_enum = sa.Enum(
        "Pending", "Running", "Success", "Failed", "Retry",
        name="taskstatus", native_enum=False
    )
    ai_call_status_enum = sa.Enum(
        "Pending", "Success", "Failed",
        name="aicallstatus", native_enum=False
    )
    application_status_enum = sa.Enum(
        "Pending", "Tailoring", "Ready", "Failed", "Applied",
        "ResumeScreened", "PhoneScreen", "Interviewing", "Offer", "Rejected",
        name="applicationstatus", native_enum=False
    )

    workflow_status_enum.create(op.get_bind(), checkfirst=True)
    task_status_enum.create(op.get_bind(), checkfirst=True)
    ai_call_status_enum.create(op.get_bind(), checkfirst=True)
    application_status_enum.create(op.get_bind(), checkfirst=True)

    # workflow_executions
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workflow_type", sa.String(length=50), nullable=False),
        sa.Column("config_version", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(
            "users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=True),
        sa.Column("status", workflow_status_enum,
                  nullable=False, server_default="Pending"),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(),
                  nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_user_status",
                    "workflow_executions", ["user_id", "status"])
    op.create_index("ix_workflow_type_status", "workflow_executions", [
                    "workflow_type", "status"])

    # task_executions
    op.create_table(
        "task_executions",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workflow_id", sa.String(length=255), sa.ForeignKey(
            "workflow_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.String(length=20),
                  nullable=False, server_default="normal"),
        sa.Column("status", task_status_enum,
                  nullable=False, server_default="Pending"),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(),
                  nullable=False, server_default="3"),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("depends_on", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_workflow_status",
                    "task_executions", ["workflow_id", "status"])
    op.create_index("ix_task_name", "task_executions", ["task_name"])

    # applications
    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(
            "users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey(
            "seek_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_resume_id", sa.String(length=255), sa.ForeignKey(
            "resumes.id", ondelete="SET NULL"), nullable=False),
        sa.Column("resume_document_id", sa.String(length=255), sa.ForeignKey(
            "documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cover_letter_document_id", sa.String(length=255), sa.ForeignKey(
            "documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", application_status_enum,
                  nullable=False, server_default="Pending"),
        sa.Column("tailoring_level", sa.String(length=50),
                  nullable=False, server_default="light"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_applications_user_job", "applications",
                    ["user_id", "job_id"], unique=True)
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_deleted", "applications", ["user_id", "is_deleted"])
    op.create_index("ix_applications_resume_doc", "applications", ["resume_document_id"])
    op.create_index("ix_applications_cover_letter_doc", "applications", ["cover_letter_document_id"])

    # outbox_events
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(),
                  nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events",
                    ["published", "created_at"])
    op.create_index("ix_outbox_aggregate", "outbox_events",
                    ["aggregate_type", "aggregate_id"])

    # ai_calls
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workflow_id", sa.String(length=255), sa.ForeignKey(
            "workflow_executions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.String(length=255), sa.ForeignKey(
            "task_executions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(
            "users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_id", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("status", ai_call_status_enum,
                  nullable=False, server_default="Pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_ai_calls_user", "ai_calls", ["user_id"])
    op.create_index("ix_ai_calls_workflow", "ai_calls", ["workflow_id"])
    op.create_index("ix_ai_calls_task", "ai_calls", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_calls_task", table_name="ai_calls")
    op.drop_index("ix_ai_calls_workflow", table_name="ai_calls")
    op.drop_index("ix_ai_calls_user", table_name="ai_calls")
    op.drop_table("ai_calls")

    op.drop_index("ix_outbox_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_unpublished", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("ix_applications_cover_letter_doc", table_name="applications")
    op.drop_index("ix_applications_resume_doc", table_name="applications")
    op.drop_index("ix_applications_deleted", table_name="applications")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_user_job", table_name="applications")
    op.drop_table("applications")

    op.drop_index("ix_task_name", table_name="task_executions")
    op.drop_index("ix_task_workflow_status", table_name="task_executions")
    op.drop_table("task_executions")

    op.drop_index("ix_workflow_type_status", table_name="workflow_executions")
    op.drop_index("ix_workflow_user_status", table_name="workflow_executions")
    op.drop_table("workflow_executions")

    sa.Enum(name="applicationstatus", native_enum=False).drop(
        op.get_bind(), checkfirst=True)
    sa.Enum(name="aicallstatus", native_enum=False).drop(
        op.get_bind(), checkfirst=True)
    sa.Enum(name="taskstatus", native_enum=False).drop(
        op.get_bind(), checkfirst=True)
    sa.Enum(name="workflowstatus", native_enum=False).drop(
        op.get_bind(), checkfirst=True)
