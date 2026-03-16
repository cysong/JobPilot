"""Fix applications source resume FK behavior

Revision ID: 8b2c4d6e9f10
Revises: f4d9a2b6c7e1
Create Date: 2026-03-16 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8b2c4d6e9f10"
down_revision: Union[str, None] = "f4d9a2b6c7e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "applications_source_resume_id_fkey",
        "applications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "applications_source_resume_id_fkey",
        "applications",
        "resumes",
        ["source_resume_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "applications_source_resume_id_fkey",
        "applications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "applications_source_resume_id_fkey",
        "applications",
        "resumes",
        ["source_resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
