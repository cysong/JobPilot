"""add avatar_seed to users

Revision ID: 7e9b3d8c2f1a
Revises: f3a5c7b9d1e4
Create Date: 2026-04-22 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e9b3d8c2f1a"
down_revision: Union[str, None] = "f3a5c7b9d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_seed", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_seed")
