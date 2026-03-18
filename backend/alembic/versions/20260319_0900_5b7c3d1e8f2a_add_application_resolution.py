"""add application resolution

Revision ID: 5b7c3d1e8f2a
Revises: 1d9f2a7c4b6e
Create Date: 2026-03-19 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b7c3d1e8f2a"
down_revision: Union[str, None] = "1d9f2a7c4b6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    application_resolution_enum = sa.Enum(
        "ACTIVE",
        "JOB_CLOSED",
        "USER_SKIPPED",
        "STALE_NO_RESPONSE",
        name="applicationresolution",
        native_enum=False,
    )
    application_resolution_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "applications",
        sa.Column(
            "resolution",
            application_resolution_enum,
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column(
        "applications",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_applications_resolution",
        "applications",
        ["resolution"],
        unique=False,
    )
    op.create_index(
        "ix_applications_user_resolution_updated_desc",
        "applications",
        ["user_id", "resolution", "updated_at"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            UPDATE applications AS a
            SET resolution = 'JOB_CLOSED',
                resolved_at = COALESCE(j.manual_expired_at, CURRENT_TIMESTAMP),
                resolution_note = COALESCE(j.manual_expired_note, 'Backfilled from manual expired job')
            FROM seek_jobs AS j
            WHERE a.job_id = j.id
              AND j.manual_expired = true
              AND a.status IN ('PENDING', 'TAILORING', 'READY')
              AND a.resolution = 'ACTIVE'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_applications_user_resolution_updated_desc", table_name="applications")
    op.drop_index("ix_applications_resolution", table_name="applications")
    op.drop_column("applications", "resolution_note")
    op.drop_column("applications", "resolved_at")
    op.drop_column("applications", "resolution")

    sa.Enum(name="applicationresolution", native_enum=False).drop(
        op.get_bind(), checkfirst=True
    )
