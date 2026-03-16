"""add manual expired fields to seek_jobs

Revision ID: f4d9a2b6c7e1
Revises: 9c1a2f4d7b8e
Create Date: 2026-03-16 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4d9a2b6c7e1"
down_revision: Union[str, None] = "9c1a2f4d7b8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seek_jobs",
        sa.Column("manual_expired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("seek_jobs", sa.Column("manual_expired_by", sa.Integer(), nullable=True))
    op.add_column("seek_jobs", sa.Column("manual_expired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("seek_jobs", sa.Column("manual_expired_note", sa.Text(), nullable=True))

    op.create_index("ix_seek_jobs_manual_expired", "seek_jobs", ["manual_expired"], unique=False)
    op.create_index("ix_seek_jobs_manual_expired_by", "seek_jobs", ["manual_expired_by"], unique=False)
    op.create_foreign_key(
        "fk_seek_jobs_manual_expired_by_users",
        "seek_jobs",
        "users",
        ["manual_expired_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("seek_jobs", "manual_expired", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_seek_jobs_manual_expired_by_users", "seek_jobs", type_="foreignkey")
    op.drop_index("ix_seek_jobs_manual_expired_by", table_name="seek_jobs")
    op.drop_index("ix_seek_jobs_manual_expired", table_name="seek_jobs")

    op.drop_column("seek_jobs", "manual_expired_note")
    op.drop_column("seek_jobs", "manual_expired_at")
    op.drop_column("seek_jobs", "manual_expired_by")
    op.drop_column("seek_jobs", "manual_expired")
