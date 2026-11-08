"""add matching v3 tables (stage 1)

Adds role family classification, job matches, admin labels and evaluation
tables, plus the resume role family binding. See docs/job_matching_v3_design.md §9.
Only creates tables and nullable columns; existing data is untouched.

Revision ID: ce72214e3bd7
Revises: a8c2e5d7b4f6
Create Date: 2026-11-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ce72214e3bd7"
down_revision: Union[str, None] = "a8c2e5d7b4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False,
                  comment="Record creation timestamp"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False,
                  comment="Record last update timestamp"),
    ]


def _jsonb(name: str, default: str | None = None, nullable: bool = True) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=nullable,
        server_default=sa.text(default) if default else None,
    )


def upgrade() -> None:
    # --- resumes: role family binding -------------------------------------
    op.add_column("resumes", sa.Column("role_family", sa.String(length=32), nullable=True))
    op.add_column("resumes", sa.Column("role_family_source", sa.String(length=8), nullable=True,
                                       comment="auto | user"))
    op.add_column("resumes", sa.Column("role_family_version", sa.String(length=16), nullable=True,
                                       comment="role_families.yaml version at binding time"))
    op.create_index(
        "ix_resumes_user_family", "resumes", ["user_id", "role_family"],
        postgresql_where=sa.text("is_draft = false AND is_deleted = false"),
    )

    # --- job_title_families -----------------------------------------------
    op.create_table(
        "job_title_families",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("title_key", sa.String(length=500), nullable=False),
        sa.Column("example_title", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("role_family", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("families_version", sa.String(length=16), nullable=False),
        sa.Column("classifier_version", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('classified','ambiguous')", name="ck_job_title_families_status"),
        sa.CheckConstraint("status <> 'classified' OR role_family IS NOT NULL",
                           name="ck_job_title_families_family"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title_key"),
    )
    op.create_index("ix_job_title_families_family", "job_title_families", ["role_family"])

    # --- job_role_families ------------------------------------------------
    op.create_table(
        "job_role_families",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("title_key", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("role_family", sa.String(length=32), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.Column("families_version", sa.String(length=16), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ai_call_id", sa.String(length=255), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('pending','classified','failed')", name="ck_job_role_families_status"),
        sa.ForeignKeyConstraint(["job_id"], ["seek_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_job_role_families_family", "job_role_families", ["role_family"],
                    postgresql_where=sa.text("status = 'classified'"))
    op.create_index("ix_job_role_families_title_key", "job_role_families", ["title_key"])
    op.create_index("ix_job_role_families_pending", "job_role_families", ["status", "created_at"],
                    postgresql_where=sa.text("status = 'pending'"))

    # --- job_matches -------------------------------------------------------
    op.create_table(
        "job_matches",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False, comment="new_job | backfill"),
        sa.Column("job_family", sa.String(length=32), nullable=False),
        sa.Column("families_version", sa.String(length=16), nullable=False),
        sa.Column("family_relation", sa.String(length=8), nullable=False, comment="same | adjacent"),
        _jsonb("candidate_resume_ids", "'[]'::jsonb", nullable=False),
        sa.Column("location_check", sa.String(length=16), nullable=False),
        sa.Column("job_listed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_content_hash", sa.String(length=64), nullable=True),
        sa.Column("resume_id", sa.String(length=255), nullable=True),
        sa.Column("resume_content_hash", sa.String(length=64), nullable=True),
        sa.Column("tier", sa.String(length=1), nullable=True),
        sa.Column("tier_reason", sa.Text(), nullable=True),
        sa.Column("tech_level", sa.String(length=8), nullable=True),
        sa.Column("experience_level", sa.String(length=8), nullable=True),
        sa.Column("reject_code", sa.String(length=24), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("reject_quote", sa.Text(), nullable=True),
        _jsonb("judgment"),
        _jsonb("validation", "'{}'::jsonb", nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("ai_call_id", sa.String(length=255), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('queued','rated','rejected','failed_retryable','failed_final','skipped_expired')",
            name="ck_job_matches_status",
        ),
        sa.CheckConstraint("tier IS NULL OR tier IN ('A','B','C','D')", name="ck_job_matches_tier"),
        sa.CheckConstraint("status <> 'rated' OR (tier IS NOT NULL AND resume_id IS NOT NULL)",
                           name="ck_job_matches_rated"),
        sa.CheckConstraint("status <> 'rejected' OR reject_code IS NOT NULL", name="ck_job_matches_rejected"),
        sa.CheckConstraint(
            "reject_code IS DISTINCT FROM 'LOCATION' OR (ai_call_id IS NULL AND location_check = 'rejected')",
            name="ck_job_matches_location_reject",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["seek_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
    )
    op.create_index("ix_job_matches_listing", "job_matches", ["user_id", "status", "tier"])
    op.create_index("ix_job_matches_queue", "job_matches", [sa.text("job_listed_at DESC")],
                    postgresql_where=sa.text("status = 'queued'"))
    op.create_index("ix_job_matches_retry", "job_matches", ["next_attempt_at"],
                    postgresql_where=sa.text("status = 'failed_retryable'"))
    op.create_index("ix_job_matches_job", "job_matches", ["job_id"])

    # --- match_labels (append-only) ----------------------------------------
    op.create_table(
        "match_labels",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("job_match_id", sa.String(length=255), nullable=True),
        sa.Column("label", sa.String(length=16), nullable=False),
        _jsonb("reason_tags", "'[]'::jsonb", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, comment="ui | import"),
        sa.Column("labeled_by", sa.Integer(), nullable=False),
        sa.Column("predicted_status", sa.String(length=20), nullable=True),
        sa.Column("predicted_tier", sa.String(length=1), nullable=True),
        sa.Column("predicted_prompt_version", sa.String(length=32), nullable=True),
        sa.Column("predicted_model", sa.String(length=64), nullable=True),
        _jsonb("predicted_snapshot"),
        sa.Column("superseded_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("label IN ('A','B','C','D','REJECT')", name="ck_match_labels_label"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["seek_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_match_id"], ["job_matches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["labeled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["superseded_by"], ["match_labels.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_labels_current", "match_labels", ["user_id", "job_id"],
                    postgresql_where=sa.text("superseded_by IS NULL"))

    # --- evaluation ----------------------------------------------------------
    op.create_table(
        "match_eval_datasets",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        _jsonb("config", nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_match_eval_datasets_name_version"),
    )
    op.create_table(
        "match_eval_items",
        sa.Column("dataset_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("item_kind", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=True),
        sa.Column("applied_resume_id", sa.String(length=255), nullable=True),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["match_eval_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("dataset_id", "user_id", "job_id"),
    )
    op.create_table(
        "match_eval_runs",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("dataset_id", sa.String(length=255), nullable=False),
        _jsonb("config", nullable=False),
        sa.Column("baseline_run_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        _jsonb("metrics"),
        sa.Column("report_md", sa.Text(), nullable=True),
        _jsonb("cost"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["match_eval_datasets.id"]),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["match_eval_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_eval_runs_dataset_started", "match_eval_runs",
                    ["dataset_id", sa.text("started_at DESC")])
    op.create_table(
        "match_eval_predictions",
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("repeat_index", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("prefilter", sa.String(length=20), nullable=False),
        sa.Column("location_check", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("tier", sa.String(length=1), nullable=True),
        sa.Column("reject_code", sa.String(length=24), nullable=True),
        sa.Column("resume_id", sa.String(length=255), nullable=True),
        _jsonb("judgment"),
        sa.ForeignKeyConstraint(["run_id"], ["match_eval_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "repeat_index", "user_id", "job_id"),
    )


def downgrade() -> None:
    op.drop_table("match_eval_predictions")
    op.drop_index("ix_match_eval_runs_dataset_started", table_name="match_eval_runs")
    op.drop_table("match_eval_runs")
    op.drop_table("match_eval_items")
    op.drop_table("match_eval_datasets")

    op.drop_index("ix_match_labels_current", table_name="match_labels")
    op.drop_table("match_labels")

    op.drop_index("ix_job_matches_job", table_name="job_matches")
    op.drop_index("ix_job_matches_retry", table_name="job_matches")
    op.drop_index("ix_job_matches_queue", table_name="job_matches")
    op.drop_index("ix_job_matches_listing", table_name="job_matches")
    op.drop_table("job_matches")

    op.drop_index("ix_job_role_families_pending", table_name="job_role_families")
    op.drop_index("ix_job_role_families_title_key", table_name="job_role_families")
    op.drop_index("ix_job_role_families_family", table_name="job_role_families")
    op.drop_table("job_role_families")

    op.drop_index("ix_job_title_families_family", table_name="job_title_families")
    op.drop_table("job_title_families")

    op.drop_index("ix_resumes_user_family", table_name="resumes")
    op.drop_column("resumes", "role_family_version")
    op.drop_column("resumes", "role_family_source")
    op.drop_column("resumes", "role_family")
