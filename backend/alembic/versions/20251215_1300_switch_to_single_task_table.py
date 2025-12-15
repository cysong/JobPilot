"""Switch to single task table model and drop workflow_executions."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1d0f0a12345"
down_revision: str | None = "eae6f0c6b418"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _drop_fk(table: str, referred_table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if fk.get("referred_table") == referred_table:
            op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    # Drop FKs that block workflow_executions removal
    _drop_fk("task_executions", "workflow_executions")
    _drop_fk("ai_calls", "workflow_executions")

    # Add new task dimension columns
    op.add_column("task_executions", sa.Column("entity_type", sa.String(length=50), nullable=True))
    op.add_column("task_executions", sa.Column("entity_id", sa.String(length=255), nullable=True))
    op.add_column("task_executions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "task_executions_user_id_fkey",
        "task_executions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Backfill from workflow_executions before dropping the table
    op.execute(
        sa.text(
            """
            UPDATE task_executions AS t
            SET
                entity_type = CASE w.workflow_type
                    WHEN 'job_analysis' THEN 'job'
                    WHEN 'resume_analysis' THEN 'resume'
                    WHEN 'cover_letter_generation' THEN 'application'
                    ELSE w.workflow_type
                END,
                entity_id = w.entity_id,
                user_id = w.user_id,
                workflow_id = COALESCE(t.workflow_id, w.id)
            FROM workflow_executions AS w
            WHERE t.workflow_id = w.id
            """
        )
    )

    # Guard against nulls from missing workflows
    op.execute(
        sa.text(
            """
            UPDATE task_executions
            SET
                entity_type = COALESCE(entity_type, 'unknown'),
                entity_id = COALESCE(entity_id, id)
            WHERE entity_type IS NULL OR entity_id IS NULL
            """
        )
    )

    # Make new columns not nullable
    op.alter_column("task_executions", "entity_type", nullable=False)
    op.alter_column("task_executions", "entity_id", nullable=False)

    # Indexes for common access patterns
    op.create_index(
        "ix_task_executions_entity",
        "task_executions",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_executions_status",
        "task_executions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_task_executions_workflow_id",
        "task_executions",
        ["workflow_id"],
        unique=False,
    )

    # Drop workflow_executions table now that references are removed
    op.drop_table("workflow_executions")


def downgrade() -> None:
    # Recreate workflow_executions table (data will not be restored)
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workflow_type", sa.String(length=50), nullable=False),
        sa.Column("config_version", sa.String(length=20), nullable=False, server_default="v1.0.0"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("entity_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="Pending"),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("max_retries", sa.Integer(), server_default="3"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Drop new indexes
    op.drop_index("ix_task_executions_workflow_id", table_name="task_executions")
    op.drop_index("ix_task_executions_status", table_name="task_executions")
    op.drop_index("ix_task_executions_entity", table_name="task_executions")

    # Make columns nullable again before removal
    op.alter_column("task_executions", "entity_type", nullable=True)
    op.alter_column("task_executions", "entity_id", nullable=True)

    # Drop FK to users and new columns
    _drop_fk("task_executions", "users")
    op.drop_column("task_executions", "user_id")
    op.drop_column("task_executions", "entity_id")
    op.drop_column("task_executions", "entity_type")

    # Restore FK references to workflow_executions
    op.create_foreign_key(
        "task_executions_workflow_id_fkey",
        "task_executions",
        "workflow_executions",
        ["workflow_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ai_calls_workflow_id_fkey",
        "ai_calls",
        "workflow_executions",
        ["workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )
