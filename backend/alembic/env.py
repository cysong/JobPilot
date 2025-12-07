"""Alembic environment configuration for async SQLAlchemy"""
from logging.config import fileConfig
import asyncio

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import your Base and all models here
from app.shared.base_model import Base
from app.core.config import settings

# Import all models for Alembic autogenerate
# IMPORTANT: All models must be imported for autogenerate to detect them
from app.modules.auth.models import User  # noqa: F401
from app.modules.jobs.models import SeekJob, JobAnalysis  # noqa: F401
from app.modules.resumes.models import Resume, Document  # noqa: F401
from app.modules.applications.models import Application, OutboxEvent  # noqa: F401
from app.modules.workflow.models import WorkflowExecution, TaskExecution, AICall  # noqa: F401

# This is the Alembic Config object
config = context.config

# Override sqlalchemy.url from environment
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Tables that should be excluded from autogenerate
# WARNING: These tables will be completely ignored by Alembic migrations
EXCLUDED_TABLES = {
    'daily_sentences',    # Legacy data - DO NOT MODIFY
    'seek_jobs1',         # Backup table - DO NOT MODIFY
    'seek_jobs',          # Protected job data - DO NOT MODIFY
}


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter objects to include/exclude from autogenerate.

    Excludes tables in EXCLUDED_TABLES from all migration operations.
    Returns False to exclude the object from autogenerate.
    """
    if type_ == "table" and name in EXCLUDED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode (async)"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
