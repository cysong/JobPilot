"""dedupe migration-introduced duplicates in application_status_history

Revision ID: f3a5c7b9d1e4
Revises: e1f3a5b7c9d2
Create Date: 2026-04-22 15:30:00.000000

Background
----------
The original backfill migration (a3f1b2c4d5e6, "add_application_status_history")
seeded rows from three different sources sequentially:

  1. tailoring_progress.status_history JSON      (UPPERCASE values)
  2. applications.applied_at                      (mixed-case "Applied" literal)
  3. applications.offered_at / rejected_at / etc. (mixed-case literals)

Blocks 2/3/4 used NOT EXISTS checks against the previously-inserted rows to
avoid duplicates, but the literals were mixed-case while block 1 had already
written UPPERCASE — so the de-dup never matched and we ended up with two
rows per (application_id, to_status) for any application that had both a
JSON history entry AND an applied_at/offered_at/rejected_at timestamp.

After migration e1f3a5b7c9d2 normalized everything to UPPER_SNAKE_CASE the
duplicates became visible (and identical-looking) in the UI.

Audit on 2026-04-22 found 117 duplicated (application_id, to_status) groups
(each with exactly one extra row): APPLIED 92, REJECTED 21, PHONE_SCREEN 3,
INTERVIEWING 1. Total rows: 678 → expected 561 after dedup.

Strategy
--------
Within each (application_id, to_status) group, keep the most informative row:

  1. Prefer rows where ``from_status IS NOT NULL`` — those came from block 3/4
     and capture the actual transition (e.g. READY → APPLIED). Block-1 rows
     have from_status NULL because the JSON history doesn't track predecessors.
  2. Tie-break on earliest ``changed_at``, then earliest ``id``.

Downgrade is a no-op: the deletion is lossy (we have no record of which IDs
were removed) and the duplicates were themselves a bug, not real history.
"""

from alembic import op


revision = "f3a5c7b9d1e4"
down_revision = "e1f3a5b7c9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM application_status_history
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY application_id, to_status
                        ORDER BY
                            CASE WHEN from_status IS NOT NULL THEN 0 ELSE 1 END,
                            changed_at,
                            id
                    ) AS rn
                FROM application_status_history
            ) ranked
            WHERE rn > 1
        )
        """
    )


def downgrade() -> None:
    # Lossy: deleted rows cannot be reconstructed. The duplicates were a
    # backfill bug, not real history, so there is nothing to restore.
    pass
