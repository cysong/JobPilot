"""add duplicate_of to job_role_families and job_matches

job_role_families.duplicate_of (one row per job, owned by matching; seek_jobs belongs
to the crawler) points a repost of the same job (another city or another
platform) at the first listing of its group. job_matches.duplicate_of points a
user's result for such a repost at the result it was copied from or merged into.
Nullable columns only; existing rows are untouched (scripts/backfill_job_duplicates.py
fills them).

Revision ID: 5d1c7a9e2b40
Revises: ce72214e3bd7
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5d1c7a9e2b40"
down_revision: Union[str, None] = "ce72214e3bd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_role_families", sa.Column(
        "duplicate_of", sa.Integer(), sa.ForeignKey("seek_jobs.id", ondelete="SET NULL"), nullable=True,
        comment="First listing of the same job (another city or platform)"))
    op.create_index("ix_job_role_families_duplicate_of", "job_role_families", ["duplicate_of"],
                    postgresql_where=sa.text("duplicate_of IS NOT NULL"))
    op.add_column("job_matches", sa.Column(
        "duplicate_of", sa.String(255), sa.ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True,
        comment="Match this result was copied from / merged into"))
    op.create_index("ix_job_matches_duplicate_of", "job_matches", ["duplicate_of"],
                    postgresql_where=sa.text("duplicate_of IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_job_matches_duplicate_of", table_name="job_matches")
    op.drop_column("job_matches", "duplicate_of")
    op.drop_index("ix_job_role_families_duplicate_of", table_name="job_role_families")
    op.drop_column("job_role_families", "duplicate_of")
