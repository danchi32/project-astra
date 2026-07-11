import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASTRA_", extra="ignore")

    app_name: str = "ASTRA Backend API"
    environment: str = "development"

    # No defaults for secrets — must come from the environment.
    database_url: str = ""
    jwt_secret_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_async_driver(cls, value: str) -> str:
        """Managed Postgres providers (Render, Neon, Heroku) hand out
        `postgres://` or `postgresql://` URLs; SQLAlchemy's async engine needs the
        asyncpg driver. Normalize so those URLs work unchanged."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                value = "postgresql+asyncpg://" + value[len("postgres://"):]
            elif value.startswith("postgresql://"):
                value = "postgresql+asyncpg://" + value[len("postgresql://"):]
        return value

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]

    # Public base URL of this backend as reached by Windows agents. Baked into the
    # generated agent installer as the default ServerUrl; the portal can override it.
    public_api_url: str = "http://localhost:8000"

    # AI engine — when the API key is unset, a deterministic stub provider is used
    # (local demo + tests run without a key or network).
    anthropic_api_key: str | None = None
    ai_model: str = "claude-opus-4-8"
    ai_max_tokens: int = 4096
    ai_max_tool_iterations: int = 6

    # Cost controls — an intent gate rejects off-topic queries before any LLM call,
    # and a semantic cache serves repeated questions from stored answers (no LLM call).
    ai_intent_gate_enabled: bool = True
    ai_cache_enabled: bool = True
    ai_cache_similarity_threshold: float = 0.85


@lru_cache
def get_settings() -> Settings:
    # Railway provides DATABASE_URL, but we expect ASTRA_DATABASE_URL with prefix
    # Fallback to DATABASE_URL if ASTRA_DATABASE_URL is not set
    astra_db_url = os.getenv("ASTRA_DATABASE_URL")
    railway_db_url = os.getenv("DATABASE_URL")

    if not astra_db_url and railway_db_url:
        print(f"[INFO] Using Railway's DATABASE_URL: {railway_db_url[:50]}...")
        os.environ["ASTRA_DATABASE_URL"] = railway_db_url

    db_url = os.getenv("ASTRA_DATABASE_URL", "NOT_SET")
    print(f"[DEBUG] ASTRA_DATABASE_URL: {db_url[:50] if db_url and db_url != 'NOT_SET' else 'EMPTY/NOT_SET'}...")

    settings = Settings()
    return settings
