"""Shared fixtures for matching v3 database tests.

Database tests run only when MATCHING_TEST_DATABASE_URL points at a throwaway
local Postgres, e.g. postgresql+asyncpg://postgres:pg@localhost:55432/migtest.
The public schema is dropped and recreated from ORM metadata for each test.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text

DB_URL = os.environ.get("MATCHING_TEST_DATABASE_URL", "")
LOCAL_DB = bool(DB_URL) and ("localhost" in DB_URL or "127.0.0.1" in DB_URL)

requires_db = pytest.mark.skipif(
    not LOCAL_DB, reason="set MATCHING_TEST_DATABASE_URL to a local throwaway Postgres to run"
)


@pytest_asyncio.fixture
async def session_factory():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.models  # noqa: F401
    from app.shared.base_model import Base

    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as db:
        yield db
