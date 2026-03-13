"""add created_at indexes for admin dashboard stats

Revision ID: 9c1a2f4d7b8e
Revises: 5e2c7d9b1a4f
Create Date: 2026-03-13 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9c1a2f4d7b8e"
down_revision: Union[str, None] = "5e2c7d9b1a4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_created_at ON users (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_seek_jobs_created_at ON seek_jobs (created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_job_matches_created_at ON user_job_matches (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_applications_created_at ON applications (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_task_executions_created_at ON task_executions (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_task_executions_created_at")
    op.execute("DROP INDEX IF EXISTS ix_applications_created_at")
    op.execute("DROP INDEX IF EXISTS ix_user_job_matches_created_at")
    op.execute("DROP INDEX IF EXISTS ix_seek_jobs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_users_created_at")
