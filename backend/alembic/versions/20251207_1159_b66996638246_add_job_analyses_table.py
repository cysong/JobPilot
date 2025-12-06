"""Add job_analyses table

Revision ID: b66996638246
Revises: a1b2c3d4e5f6
Create Date: 2025-12-07 11:59:17.174853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b66996638246'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job_analyses table
    op.create_table(
        'job_analyses',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False, comment='Reference to analyzed job'),

        # Skills Requirements
        sa.Column('required_skills', sa.JSON(), nullable=False, server_default='[]', comment='Must-have technical skills'),
        sa.Column('preferred_skills', sa.JSON(), nullable=False, server_default='[]', comment='Nice-to-have skills'),
        sa.Column('certifications', sa.JSON(), nullable=False, server_default='[]', comment='Required or preferred certifications'),
        sa.Column('tech_stack', sa.JSON(), nullable=False, server_default='[]', comment='Technologies, frameworks, and tools'),

        # Responsibilities & Requirements
        sa.Column('seniority', sa.String(length=50), nullable=True, comment='Seniority level (Junior, Mid, Senior, Lead)'),
        sa.Column('key_responsibilities', sa.JSON(), nullable=False, server_default='[]', comment='Main job responsibilities (3-5 key points)'),
        sa.Column('experience_years', sa.String(length=50), nullable=True, comment="Required experience (e.g., '3-5 years', '5+ years')"),
        sa.Column('education_requirement', sa.String(length=200), nullable=True, comment='Education requirement'),

        # Soft Requirements
        sa.Column('soft_skills', sa.JSON(), nullable=False, server_default='[]', comment='Soft skills (teamwork, communication, etc.)'),
        sa.Column('company_culture_keywords', sa.JSON(), nullable=False, server_default='[]', comment='Company culture descriptors'),

        # Agent Inference
        sa.Column('hiring_priorities', sa.JSON(), nullable=False, server_default='[]', comment="Agent's inference: what does company value most? (top 3)"),

        # Metadata
        sa.Column('analysis_version', sa.String(length=20), nullable=False, server_default='v1.0.0', comment='Analysis schema version for future compatibility'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        # Constraints
        sa.PrimaryKeyConstraint('id', name='job_analyses_pkey'),
        sa.ForeignKeyConstraint(['job_id'], ['seek_jobs.id'], name='job_analyses_job_id_fkey', ondelete='CASCADE'),
        sa.UniqueConstraint('job_id', name='job_analyses_job_id_unique'),
    )

    # Create index
    op.create_index('ix_job_analyses_job_id', 'job_analyses', ['job_id'], unique=False)


def downgrade() -> None:
    # Drop table and index
    op.drop_index('ix_job_analyses_job_id', table_name='job_analyses')
    op.drop_table('job_analyses')
