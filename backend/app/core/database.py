"""Database connection and session management"""
from uuid import uuid4

from contextvars import ContextVar

from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from app.core.config import settings


def _is_supabase_transaction_pooler(database_url: str) -> bool:
    url = make_url(database_url)
    return bool(url.host and url.host.endswith(".pooler.supabase.com") and url.port == 6543)


database_url = settings.DATABASE_URL
database_url_parsed = make_url(database_url)
is_supabase_transaction_pooler = _is_supabase_transaction_pooler(database_url)

connect_args: dict[str, object] = {}
engine_kwargs: dict[str, object] = {
    "echo": settings.ENVIRONMENT == "development",
    "pool_pre_ping": True,
}

if is_supabase_transaction_pooler:
    engine_kwargs["poolclass"] = NullPool
    connect_args["prepared_statement_name_func"] = (
        lambda: f"__asyncpg_{uuid4()}__"
    )
    if "prepared_statement_cache_size" not in database_url_parsed.query:
        connect_args["prepared_statement_cache_size"] = 0
else:
    # Supabase's session pooler caps clients per project (15 on this plan) and every
    # pooled connection holds one slot: size each process so api + worker + a
    # migration fit. A full pool makes callers wait (pool_timeout) instead of erroring.
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT

# Create async engine
engine = create_async_engine(
    database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Sessions opened by the workflow task running in this context (AsyncBaseTask.session).
# The LLM gateway checks them: none may hold an open transaction during a model call.
task_sessions: ContextVar[list[AsyncSession] | None] = ContextVar("task_sessions", default=None)


def sessions_in_transaction() -> list[AsyncSession]:
    """This task's sessions that currently hold an open transaction (a pinned connection)."""
    return [db for db in (task_sessions.get() or ()) if db.in_transaction()]
