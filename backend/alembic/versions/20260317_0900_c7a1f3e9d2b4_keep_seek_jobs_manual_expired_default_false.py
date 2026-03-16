"""keep seek_jobs manual_expired default false

Revision ID: c7a1f3e9d2b4
Revises: 8b2c4d6e9f10
Create Date: 2026-03-17 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a1f3e9d2b4"
down_revision: Union[str, None] = "8b2c4d6e9f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE seek_jobs
            SET manual_expired = false
            WHERE manual_expired IS NULL
            """
        )
    )

    op.alter_column(
        "seek_jobs",
        "manual_expired",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )


def downgrade() -> None:
    op.alter_column(
        "seek_jobs",
        "manual_expired",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )
