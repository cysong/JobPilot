"""add application_status_history table

Revision ID: a3f1b2c4d5e6
Revises: b4f2c8d9e1a7
Create Date: 2026-04-13 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f1b2c4d5e6"
down_revision: Union[str, None] = "b4f2c8d9e1a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_status_history",
        sa.Column("id", sa.String(255), nullable=False),
        sa.Column("application_id", sa.String(255), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_status_history_application_id",
        "application_status_history",
        ["application_id"],
    )
    op.create_index(
        "ix_status_history_changed_at",
        "application_status_history",
        ["changed_at"],
    )

    # --- Backfill from existing tailoring_progress.status_history JSON ---
    # These are user-triggered transitions recorded before this migration.
    op.execute(sa.text("""
        INSERT INTO application_status_history
            (id, application_id, from_status, to_status, changed_at, changed_by_id, note)
        SELECT
            gen_random_uuid()::text,
            a.id,
            NULLIF(entry->>'from_status', ''),
            entry->>'to_status',
            (entry->>'changed_at')::timestamptz,
            NULLIF(entry->>'operator_user_id', '')::integer,
            NULLIF(entry->>'note', '')
        FROM applications a,
             jsonb_array_elements(
                 CASE
                     WHEN a.tailoring_progress IS NOT NULL
                      AND a.tailoring_progress::jsonb ? 'status_history'
                      AND jsonb_typeof(a.tailoring_progress::jsonb->'status_history') = 'array'
                     THEN a.tailoring_progress::jsonb->'status_history'
                     ELSE '[]'::jsonb
                 END
             ) AS entry
        WHERE entry->>'to_status' IS NOT NULL
    """))

    # --- Backfill Pending entry (creation) for every application ---
    # Uses created_at; user_id is always the owner.
    op.execute(sa.text("""
        INSERT INTO application_status_history
            (id, application_id, from_status, to_status, changed_at, changed_by_id, note)
        SELECT
            gen_random_uuid()::text,
            a.id,
            NULL,
            'Pending',
            a.created_at,
            a.user_id,
            NULL
        FROM applications a
        WHERE NOT EXISTS (
            SELECT 1 FROM application_status_history h
            WHERE h.application_id = a.id
              AND h.to_status = 'Pending'
              AND h.from_status IS NULL
        )
    """))

    # --- Backfill Applied entry from applied_at (reliable dedicated field) ---
    op.execute(sa.text("""
        INSERT INTO application_status_history
            (id, application_id, from_status, to_status, changed_at, changed_by_id, note)
        SELECT
            gen_random_uuid()::text,
            a.id,
            'Ready',
            'Applied',
            a.applied_at,
            a.user_id,
            NULL
        FROM applications a
        WHERE a.applied_at IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM application_status_history h
            WHERE h.application_id = a.id AND h.to_status = 'Applied'
        )
    """))

    # --- Backfill Offer entry from offered_at (reliable dedicated field) ---
    op.execute(sa.text("""
        INSERT INTO application_status_history
            (id, application_id, from_status, to_status, changed_at, changed_by_id, note)
        SELECT
            gen_random_uuid()::text,
            a.id,
            'Interviewing',
            'Offer',
            a.offered_at,
            a.user_id,
            NULL
        FROM applications a
        WHERE a.offered_at IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM application_status_history h
            WHERE h.application_id = a.id AND h.to_status = 'Offer'
        )
    """))

    # --- Fallback: current status entry if not already covered ---
    # Uses updated_at as an approximation for status transitions not recorded above.
    op.execute(sa.text("""
        INSERT INTO application_status_history
            (id, application_id, from_status, to_status, changed_at, changed_by_id, note)
        SELECT
            gen_random_uuid()::text,
            a.id,
            NULL,
            a.status,
            a.updated_at,
            a.user_id,
            NULL
        FROM applications a
        WHERE a.status != 'Pending'
          AND NOT EXISTS (
            SELECT 1 FROM application_status_history h
            WHERE h.application_id = a.id AND h.to_status = a.status
        )
    """))


def downgrade() -> None:
    op.drop_index("ix_status_history_changed_at", table_name="application_status_history")
    op.drop_index("ix_status_history_application_id", table_name="application_status_history")
    op.drop_table("application_status_history")
