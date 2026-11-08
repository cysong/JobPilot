"""Verify the matching v3 migration against a throwaway Postgres.

Builds the pre-migration schema (all ORM tables minus the v3 additions),
stamps the previous revision, runs ``alembic upgrade head``, and checks that
the resulting schema matches the ORM metadata for every v3 object. Then
downgrades one revision and checks everything is removed, and upgrades again.

Usage (never point this at a real database; it drops tables):
    DATABASE_URL=postgresql+asyncpg://postgres:pg@localhost:55432/migtest \
        uv run python -m scripts.verify_matching_v3_migration
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  register all models
from app.shared.base_model import Base

PREVIOUS_REVISION = "a8c2e5d7b4f6"
NEW_TABLES = [
    "match_eval_predictions", "match_eval_runs", "match_eval_items", "match_eval_datasets",
    "match_labels", "job_matches", "job_role_families", "job_title_families",
]
NEW_RESUME_COLUMNS = ["role_family", "role_family_source", "role_family_version"]


def _alembic(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True)


def _v3_diffs(diffs: list) -> list:
    """Keep only autogenerate diffs that concern v3 objects."""
    relevant = []
    for diff in diffs:
        flat = diff if isinstance(diff, tuple) else diff[0]
        blob = repr(flat)
        if any(t in blob for t in NEW_TABLES) or any(c in blob for c in NEW_RESUME_COLUMNS) \
                or "ix_resumes_user_family" in blob:
            relevant.append(diff)
    return relevant


async def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if "localhost" not in url and "127.0.0.1" not in url:
        print("Refusing to run: DATABASE_URL must point at a local throwaway database.")
        return 2

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
        # Rewind to the pre-v3 schema.
        for table in NEW_TABLES:
            await conn.execute(text(f"DROP TABLE {table} CASCADE"))
        await conn.execute(text("DROP INDEX ix_resumes_user_family"))
        for column in NEW_RESUME_COLUMNS:
            await conn.execute(text(f"ALTER TABLE resumes DROP COLUMN {column}"))
    await engine.dispose()

    _alembic("stamp", PREVIOUS_REVISION)
    _alembic("upgrade", "head")

    engine = create_async_engine(url)
    async with engine.connect() as conn:
        diffs = await conn.run_sync(
            lambda sync_conn: compare_metadata(MigrationContext.configure(sync_conn), Base.metadata)
        )
    await engine.dispose()
    relevant = _v3_diffs(diffs)
    if relevant:
        print("Schema after upgrade differs from ORM metadata:")
        for diff in relevant:
            print("  ", diff)
        return 1
    print("upgrade: schema matches ORM metadata for all v3 objects")

    _alembic("downgrade", "-1")
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        tables, resume_cols = await conn.run_sync(
            lambda c: (set(inspect(c).get_table_names()), {col["name"] for col in inspect(c).get_columns("resumes")})
        )
    await engine.dispose()
    leftovers = (set(NEW_TABLES) & tables) | (set(NEW_RESUME_COLUMNS) & resume_cols)
    if leftovers:
        print(f"downgrade left objects behind: {sorted(leftovers)}")
        return 1
    print("downgrade: all v3 objects removed")

    _alembic("upgrade", "head")
    print("re-upgrade: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
