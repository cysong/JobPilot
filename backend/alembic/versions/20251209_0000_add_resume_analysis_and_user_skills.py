"""Add resume analysis fields and user_skills table.

Revision ID: add_resume_analysis_user_skills
Revises: 0747b17e4371
Create Date: 2025-12-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_resume_analysis_user_skills"
down_revision: Union[str, None] = "0747b17e4371"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add analysis fields to resumes
    op.add_column("resumes", sa.Column("analysis_result", sa.JSON(), nullable=True))
    op.add_column("resumes", sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("resumes", sa.Column("analysis_version", sa.String(length=20), nullable=True))
    op.create_index("ix_resumes_analyzed_at", "resumes", ["analyzed_at"], unique=False)

    # Create user_skills table
    op.create_table(
        "user_skills",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("skill_name", sa.String(length=200), nullable=False),
        sa.Column("proficiency", sa.String(length=20), nullable=False),
        sa.Column("skill_type", sa.String(length=50), nullable=False, server_default="technical"),
        sa.Column("extracted_from_id", sa.String(length=255), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "skill_name", name="uq_user_skills_user_skill"),
    )
    op.create_index("ix_user_skills_user_skill_type", "user_skills", ["user_id", "skill_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_skills_user_skill_type", table_name="user_skills")
    op.drop_table("user_skills")
    op.drop_index("ix_resumes_analyzed_at", table_name="resumes")
    op.drop_column("resumes", "analysis_version")
    op.drop_column("resumes", "analyzed_at")
    op.drop_column("resumes", "analysis_result")
