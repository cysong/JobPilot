"""add user_job_views table

Revision ID: 5e2c7d9b1a4f
Revises: 7f4d2c9ab1e0
Create Date: 2026-03-13 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e2c7d9b1a4f"
down_revision: Union[str, None] = "7f4d2c9ab1e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_job_views",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["seek_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_job_views_user_job"),
    )

    op.create_index("ix_user_job_views_user_id", "user_job_views", ["user_id"], unique=False)
    op.create_index("ix_user_job_views_job_id", "user_job_views", ["job_id"], unique=False)
    op.create_index("ix_user_job_views_first_viewed_at", "user_job_views", ["first_viewed_at"], unique=False)
    op.create_index("ix_user_job_views_last_viewed_at", "user_job_views", ["last_viewed_at"], unique=False)
    op.create_index(
        "ix_user_job_views_user_last_viewed",
        "user_job_views",
        ["user_id", "last_viewed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_job_views_user_last_viewed", table_name="user_job_views")
    op.drop_index("ix_user_job_views_last_viewed_at", table_name="user_job_views")
    op.drop_index("ix_user_job_views_first_viewed_at", table_name="user_job_views")
    op.drop_index("ix_user_job_views_job_id", table_name="user_job_views")
    op.drop_index("ix_user_job_views_user_id", table_name="user_job_views")
    op.drop_table("user_job_views")