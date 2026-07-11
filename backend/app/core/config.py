import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASTRA_", extra="ignore")

    app_name: str = "ASTRA Backend API"
    environment: str = "development"

    # No defaults for secrets — must come from the environment.
    database_url: str
    jwt_secret_key: str

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_async_driver(cls, value: str) -> str:
        """Managed Postgres providers (Railway, Render, Neon, Heroku) hand out
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


def _ensure_database_url() -> None:
    """Railway's Postgres plugin exposes the connection string as DATABASE_URL.
    We expect ASTRA_DATABASE_URL (env_prefix). Bridge the two so either works,
    and fail with a clear, actionable message if neither is set."""
    astra_url = os.getenv("ASTRA_DATABASE_URL", "").strip()
    railway_url = os.getenv("DATABASE_URL", "").strip()

    if not astra_url and railway_url:
        os.environ["ASTRA_DATABASE_URL"] = railway_url
        astra_url = railway_url

    if not astra_url:
        raise RuntimeError(
            "No database URL found. Set ASTRA_DATABASE_URL (or DATABASE_URL) in the "
            "Railway backend service Variables tab to your Postgres connection string, "
            "e.g. postgresql://user:pass@host:port/dbname"
        )

    # Masked diagnostic so the deploy logs prove what was read, without leaking the password.
    scheme, _, rest = astra_url.partition("://")
    host_part = rest.split("@")[-1] if "@" in rest else rest
    print(f"[config] database_url resolved: scheme={scheme}, host={host_part}, length={len(astra_url)}")


@lru_cache
def get_settings() -> Settings:
    _ensure_database_url()
    return Settings()
