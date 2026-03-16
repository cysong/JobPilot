# Migration Checklist

**Purpose:** prevent schema changes from breaking runtime writes, especially on tables shared with external systems.

---

## 1. Classify the Table First

Before writing a migration, decide which category the target table belongs to:

- Internal-write table
  - only JobPilot writes to it
- Shared-write table
  - another system may insert or update rows directly

For this project, the current known shared-write table is:
- `seek_jobs`

This table is written by the external crawler system and read by JobPilot.

---

## 2. Rule for Shared-Write Tables

For any new column added to a shared-write table:

- the column must be `nullable=True`
- or it must have a database `server_default`

Do not rely only on ORM-side `default=...`.

Reason:
- ORM defaults only help when data is inserted through SQLAlchemy
- external systems writing directly to the database do not benefit from ORM defaults
- missing database defaults on non-null new columns can break external inserts immediately

### Required Rule

For `seek_jobs`, every newly added column must satisfy one of these:

1. `nullable=True`
2. `nullable=False` with a safe `server_default`

---

## 3. Safe Patterns

### Pattern A: Nullable New Column

Use when the new field is optional and existing writers will not populate it immediately.

```python
op.add_column(
    "seek_jobs",
    sa.Column("example_note", sa.Text(), nullable=True),
)
```

### Pattern B: Non-null New Column With Database Default

Use when the field must always have a value.

```python
op.add_column(
    "seek_jobs",
    sa.Column(
        "example_flag",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    ),
)
```

If historical rows may contain nulls, backfill before tightening constraints:

```python
op.execute(
    sa.text(
        """
        UPDATE seek_jobs
        SET example_flag = false
        WHERE example_flag IS NULL
        """
    )
)
```

---

## 4. Do Not Remove Shared-Table Defaults Lightly

For shared-write tables, do **not** drop a database default after creating the column unless you are certain:

- all external writers now explicitly provide the field
- and removing the default will not break inserts

This is the exact issue fixed for:
- `seek_jobs.manual_expired`

Bad pattern:

```python
op.add_column(
    "seek_jobs",
    sa.Column("manual_expired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
)
op.alter_column("seek_jobs", "manual_expired", server_default=None)
```

Preferred pattern for shared-write tables:

```python
op.add_column(
    "seek_jobs",
    sa.Column("manual_expired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
)
```

---

## 5. ORM Mapping Rule

If a shared-write table column depends on a database default, keep the model definition aligned:

```python
manual_expired: Mapped[Optional[bool]] = mapped_column(
    Boolean,
    default=False,
    server_default=sa.text("false"),
    nullable=False,
)
```

Why:
- keeps Alembic autogenerate from trying to remove the default again
- makes model intent match actual database behavior

---

## 6. Existing Data Safety

When introducing a new non-null field or changing nullable behavior:

1. backfill historical nulls first
2. then apply the constraint/default change

Checklist:

- Are there existing rows where the column may be `NULL`?
- Is there a safe backfill value?
- Is the backfill idempotent?

Example:

```python
op.execute(
    sa.text(
        """
        UPDATE seek_jobs
        SET manual_expired = false
        WHERE manual_expired IS NULL
        """
    )
)
```

---

## 7. Foreign Key Safety on Shared Tables

When adding foreign keys to shared-write tables:

- prefer `nullable=True` unless the external writer can always provide the value
- if using `ondelete`, ensure it matches nullable behavior

Safe example:

```python
op.add_column("seek_jobs", sa.Column("manual_expired_by", sa.Integer(), nullable=True))
op.create_foreign_key(
    "fk_seek_jobs_manual_expired_by_users",
    "seek_jobs",
    "users",
    ["manual_expired_by"],
    ["id"],
    ondelete="SET NULL",
)
```

Unsafe combination:

- `nullable=False`
- with `ondelete="SET NULL"`

---

## 8. Pre-Merge Checklist

Before merging any migration that touches `seek_jobs`, confirm:

- Is every new column nullable or backed by `server_default`?
- If non-null, is the default defined at the database level?
- If changing a column to non-null, are historical nulls backfilled first?
- Does the ORM model include `server_default` where needed?
- Did you avoid removing a shared-table default without explicit external-writer confirmation?
- Do foreign key delete rules match nullable behavior?

---

## 9. Post-Migration Verification

After applying the migration, verify:

1. schema
   - new column nullability/defaults are correct
2. historical data
   - no unexpected nulls remain
3. external writer safety
   - inserts that omit the new field still succeed

Recommended SQL checks:

```sql
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'seek_jobs'
  AND column_name IN ('manual_expired', 'manual_expired_by', 'manual_expired_at', 'manual_expired_note');
```

```sql
SELECT COUNT(*)
FROM seek_jobs
WHERE manual_expired IS NULL;
```

---

## 10. Current Project Note

As of 2026-03-17:

- shared-write table confirmed: `seek_jobs`
- protected field:
  - `manual_expired` must keep database default `false`
- nullable companion fields:
  - `manual_expired_by`
  - `manual_expired_at`
  - `manual_expired_note`

Future changes to `seek_jobs` should follow this checklist by default.
