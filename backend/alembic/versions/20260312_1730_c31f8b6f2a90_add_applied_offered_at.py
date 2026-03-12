"""add applied_at and offered_at to applications

Revision ID: c31f8b6f2a90
Revises: a4c9d8e71f01
Create Date: 2026-03-12 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c31f8b6f2a90"
down_revision: Union[str, None] = "a4c9d8e71f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_applications_applied_at", "applications", ["applied_at"], unique=False)
    op.create_index("ix_applications_offered_at", "applications", ["offered_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_applications_offered_at", table_name="applications")
    op.drop_index("ix_applications_applied_at", table_name="applications")
    op.drop_column("applications", "offered_at")
    op.drop_column("applications", "applied_at")
