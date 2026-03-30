"""Database connection and session management"""
from uuid import uuid4

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
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

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
