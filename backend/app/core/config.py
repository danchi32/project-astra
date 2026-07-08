from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASTRA_", extra="ignore")

    app_name: str = "ASTRA Backend API"
    environment: str = "development"

    # No defaults for secrets — must come from the environment.
    database_url: str
    jwt_secret_key: str

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]

    # AI engine — when the API key is unset, a deterministic stub provider is used
    # (local demo + tests run without a key or network).
    anthropic_api_key: str | None = None
    ai_model: str = "claude-opus-4-8"
    ai_max_tokens: int = 4096
    ai_max_tool_iterations: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
