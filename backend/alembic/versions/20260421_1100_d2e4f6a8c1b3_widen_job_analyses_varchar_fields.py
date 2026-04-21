"""widen job_analyses seniority / experience_years to 200

Revision ID: d2e4f6a8c1b3
Revises: a3f1b2c4d5e6
Create Date: 2026-04-21 11:00:00.000000

LLM output for these two fields is naturally a short phrase (e.g. "Senior",
"5+ years"), but occasionally expands into compound descriptions like
"5+ years clinical practice; 5+ years Medical Affairs" (52 chars) which
overflows the original VARCHAR(50) and raises StringDataRightTruncationError,
failing the whole analysis insert. We bump both columns to 200 to match
`education_requirement` and give headroom without silently truncating.

No data backfill needed — we're only widening, so existing rows fit unchanged.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e4f6a8c1b3"
down_revision: Union[str, None] = "a3f1b2c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "job_analyses",
        "seniority",
        existing_type=sa.String(length=50),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.alter_column(
        "job_analyses",
        "experience_years",
        existing_type=sa.String(length=50),
        type_=sa.String(length=200),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Before narrowing, clip any rows that would otherwise error on the
    # ALTER. Anything over 50 chars is LLM verbosity we can safely
    # truncate — downgrade is a rollback path, not a lossless op.
    op.execute(sa.text(
        "UPDATE job_analyses SET seniority = left(seniority, 50) "
        "WHERE seniority IS NOT NULL AND char_length(seniority) > 50"
    ))
    op.execute(sa.text(
        "UPDATE job_analyses SET experience_years = left(experience_years, 50) "
        "WHERE experience_years IS NOT NULL AND char_length(experience_years) > 50"
    ))
    op.alter_column(
        "job_analyses",
        "experience_years",
        existing_type=sa.String(length=200),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "job_analyses",
        "seniority",
        existing_type=sa.String(length=200),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
