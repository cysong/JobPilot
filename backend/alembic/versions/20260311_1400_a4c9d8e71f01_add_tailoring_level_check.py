"""add tailoring_level check constraint

Revision ID: a4c9d8e71f01
Revises: 5ad4fc7e9426
Create Date: 2026-03-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4c9d8e71f01"
down_revision: Union[str, None] = "5ad4fc7e9426"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize existing invalid values before adding constraint.
    op.execute(
        sa.text(
            """
            UPDATE applications
            SET tailoring_level = 'light'
            WHERE tailoring_level IS NULL
               OR tailoring_level NOT IN ('light', 'moderate', 'deep')
            """
        )
    )
    op.create_check_constraint(
        "ck_applications_tailoring_level",
        "applications",
        "tailoring_level IN ('light', 'moderate', 'deep')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_applications_tailoring_level", "applications", type_="check")
