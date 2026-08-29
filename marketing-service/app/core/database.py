from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()


def _engine_kwargs() -> dict[str, Any]:
    """Pool tuning for the real (Postgres) engine.

    Smaller than the product backend's on purpose. This service handles a handful of
    requests a day, so a large pool would only hold idle connections open against Neon's
    limit for no benefit. `pool_pre_ping` matters more here than there: with traffic this
    sparse, almost every request arrives after the compute has scaled to zero and come
    back, and without the ping the first lead of the day is handed a dead connection.

    SQLite (tests) accepts none of these arguments, so they only apply to Postgres URLs.
    """
    if _settings.database_url.startswith("sqlite"):
        return {}
    return {
        "pool_size": _settings.db_pool_size,
        "max_overflow": _settings.db_max_overflow,
        "pool_recycle": _settings.db_pool_recycle_seconds,
        "pool_pre_ping": _settings.db_pool_pre_ping,
    }


engine = create_async_engine(_settings.database_url, **_engine_kwargs())
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
