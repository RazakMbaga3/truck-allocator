"""
app/alembic/env.py — Alembic migration environment.

Supports async SQLAlchemy engine (required for aiosqlite / asyncpg).
DATABASE_URL is pulled from app settings so we always migrate the same
database the app connects to.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

# Import all models so their metadata is registered on Base
import app.models  # noqa: F401
from app.database import Base

config = context.config
settings = get_settings()

# Override the sqlalchemy.url from alembic.ini with the real app setting
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async engine)."""
    connect_args = {}
    if "sqlite" in settings.database_url:
        connect_args = {"check_same_thread": False}

    engine = create_async_engine(settings.database_url, connect_args=connect_args)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
