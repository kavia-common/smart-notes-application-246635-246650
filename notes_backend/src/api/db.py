from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.api.config import get_settings


def _is_sqlite_memory(url: str) -> bool:
    return url.startswith("sqlite+aiosqlite:///:memory:")


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create and cache the application's AsyncEngine."""
    settings = get_settings()

    # SQLite in-memory needs StaticPool so all connections share the same DB.
    if _is_sqlite_memory(settings.database_url):
        return create_async_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Create and cache an async sessionmaker."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


# PUBLIC_INTERFACE
async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an AsyncSession."""
    async with get_session_maker()() as session:
        yield session


# PUBLIC_INTERFACE
async def init_db_schema() -> None:
    """
    Create database tables from SQLAlchemy metadata (dev/tests only).

    Production deployments should rely on the `notes_database` container schema initializer.
    """
    from src.api.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
