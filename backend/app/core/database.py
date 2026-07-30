from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()


def _engine_kwargs() -> dict[str, Any]:
    """Pool tuning for the real (Postgres) engine.

    SQLAlchemy's defaults (5 + 10 overflow, no liveness check) are fine for a single
    long-lived instance but wrong for this deployment in two ways:

    * `pool_pre_ping` — Neon scales its compute to zero after ~5 minutes idle and
      restarts weekly for updates. Without a pre-ping, the first request after either
      event is handed a dead connection and fails.
    * `pool_recycle` — poolers and managed providers drop idle connections silently;
      recycling before that keeps us from discovering it mid-request.

    SQLite (tests, the local demo) uses a pool that accepts none of these arguments, so
    they're only applied to Postgres URLs.
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
