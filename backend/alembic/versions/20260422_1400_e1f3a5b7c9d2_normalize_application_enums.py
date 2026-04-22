"""normalize ApplicationStatus / Resolution to native PG ENUM (UPPER_SNAKE_CASE)

Revision ID: e1f3a5b7c9d2
Revises: d2e4f6a8c1b3
Create Date: 2026-04-22 14:00:00.000000

Background
----------
ApplicationStatus historically had divergent enum name (UPPER_SNAKE_CASE)
and value (mixed-case CamelCase). The Application.status column was
declared as ``SQLEnum(..., native_enum=False)`` *without* values_callable,
so SQLAlchemy silently stored the enum *name* — meaning DB rows held
``PHONE_SCREEN`` while application code, Pydantic, and the frontend all
expected the value ``PhoneScreen``. The mismatch was masked by SQLAlchemy
mapping names back to enum members on read, but it surfaced once the
status_history table started feeding raw strings into Pydantic
(StatusHistoryEntry), which produced 500s.

This migration converges the entire stack on the project convention:
  * enum name == value, UPPER_SNAKE_CASE
  * native PostgreSQL ENUM types (created here)
  * application_status_history columns share the same PG ENUM type as
    applications.status (single source of truth for valid values)

Data normalization is required for application_status_history.to_status /
from_status only — those columns hold a mix of mixed-case repo writes and
uppercase backfill values. applications.status already stored uppercase
names so it just needs the type swap. applications.resolution was already
canonical (name == value); same — just a type swap.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f3a5b7c9d2"
down_revision: Union[str, None] = "d2e4f6a8c1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mixed-case (legacy enum value) → UPPER_SNAKE_CASE (new canonical value).
# Values already in UPPER form are unaffected.
STATUS_RENAME = {
    "Pending": "PENDING",
    "Tailoring": "TAILORING",
    "Ready": "READY",
    "Applied": "APPLIED",
    "PhoneScreen": "PHONE_SCREEN",
    "Interviewing": "INTERVIEWING",
    "Offer": "OFFER",
    "Rejected": "REJECTED",
    "Failed": "FAILED",
}

NEW_STATUS_VALUES = list(STATUS_RENAME.values())
NEW_RESOLUTION_VALUES = ["ACTIVE", "JOB_CLOSED", "USER_SKIPPED", "STALE_NO_RESPONSE"]


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Normalize string data (columns are still VARCHAR at this point).
    for old, new in STATUS_RENAME.items():
        if old == new:
            continue
        # applications.status was already storing uppercase names due to
        # the missing values_callable, so the UPDATE here is a no-op for
        # most rows — the SET still runs cheaply on ~200 rows.
        bind.execute(
            sa.text("UPDATE applications SET status = :new WHERE status = :old"),
            {"old": old, "new": new},
        )
        bind.execute(
            sa.text(
                "UPDATE application_status_history "
                "SET to_status = :new WHERE to_status = :old"
            ),
            {"old": old, "new": new},
        )
        bind.execute(
            sa.text(
                "UPDATE application_status_history "
                "SET from_status = :new WHERE from_status = :old"
            ),
            {"old": old, "new": new},
        )

    # 2. Drop the old VARCHAR server_defaults — they cannot be cast to
    #    the new ENUM types in step 4.
    op.alter_column("applications", "status", server_default=None)
    op.alter_column("applications", "resolution", server_default=None)

    # 3. Create the native PG ENUM types.
    application_status = sa.Enum(*NEW_STATUS_VALUES, name="application_status")
    application_resolution = sa.Enum(*NEW_RESOLUTION_VALUES, name="application_resolution")
    application_status.create(bind, checkfirst=True)
    application_resolution.create(bind, checkfirst=True)

    # 4. Convert columns VARCHAR → ENUM. The USING cast works because
    #    every existing row is already in NEW_STATUS_VALUES / NEW_RESOLUTION_VALUES.
    op.alter_column(
        "applications",
        "status",
        type_=application_status,
        existing_nullable=False,
        postgresql_using="status::application_status",
        server_default=sa.text("'PENDING'::application_status"),
    )
    op.alter_column(
        "applications",
        "resolution",
        type_=application_resolution,
        existing_nullable=False,
        postgresql_using="resolution::application_resolution",
        server_default=sa.text("'ACTIVE'::application_resolution"),
    )
    op.alter_column(
        "application_status_history",
        "to_status",
        type_=application_status,
        existing_nullable=False,
        postgresql_using="to_status::application_status",
    )
    op.alter_column(
        "application_status_history",
        "from_status",
        type_=application_status,
        existing_nullable=True,
        postgresql_using="from_status::application_status",
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Revert columns to VARCHAR. Drop server_defaults first so the type
    # change does not trip on a default cast.
    op.alter_column("applications", "status", server_default=None)
    op.alter_column("applications", "resolution", server_default=None)

    op.alter_column(
        "application_status_history",
        "from_status",
        type_=sa.String(length=50),
        existing_nullable=True,
        postgresql_using="from_status::text",
    )
    op.alter_column(
        "application_status_history",
        "to_status",
        type_=sa.String(length=50),
        existing_nullable=False,
        postgresql_using="to_status::text",
    )
    op.alter_column(
        "applications",
        "resolution",
        type_=sa.String(length=50),
        existing_nullable=False,
        postgresql_using="resolution::text",
        server_default=sa.text("'ACTIVE'::character varying"),
    )
    op.alter_column(
        "applications",
        "status",
        type_=sa.String(length=50),
        existing_nullable=False,
        postgresql_using="status::text",
        server_default=sa.text("'Pending'::character varying"),
    )

    # Map values back to the old mixed-case form.
    for old, new in STATUS_RENAME.items():
        if old == new:
            continue
        bind.execute(
            sa.text("UPDATE applications SET status = :old WHERE status = :new"),
            {"old": old, "new": new},
        )
        bind.execute(
            sa.text(
                "UPDATE application_status_history "
                "SET to_status = :old WHERE to_status = :new"
            ),
            {"old": old, "new": new},
        )
        bind.execute(
            sa.text(
                "UPDATE application_status_history "
                "SET from_status = :old WHERE from_status = :new"
            ),
            {"old": old, "new": new},
        )

    sa.Enum(name="application_status").drop(bind, checkfirst=True)
    sa.Enum(name="application_resolution").drop(bind, checkfirst=True)
