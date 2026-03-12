"""add user_saved_jobs table

Revision ID: 7f4d2c9ab1e0
Revises: c31f8b6f2a90
Create Date: 2026-03-12 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f4d2c9ab1e0"
down_revision: Union[str, None] = "c31f8b6f2a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_saved_jobs",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["seek_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_saved_jobs_user_job"),
    )
    op.create_index("ix_user_saved_jobs_user_id", "user_saved_jobs", ["user_id"], unique=False)
    op.create_index("ix_user_saved_jobs_job_id", "user_saved_jobs", ["job_id"], unique=False)
    op.create_index("ix_user_saved_jobs_created_at", "user_saved_jobs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_saved_jobs_created_at", table_name="user_saved_jobs")
    op.drop_index("ix_user_saved_jobs_job_id", table_name="user_saved_jobs")
    op.drop_index("ix_user_saved_jobs_user_id", table_name="user_saved_jobs")
    op.drop_table("user_saved_jobs")
