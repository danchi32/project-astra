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

    # Billing (Stripe) — all optional. When the secret key + price id are unset,
    # billing is INERT: the endpoints report "not configured" and nothing charges.
    # Set these (test keys first) to switch billing on without any code change.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None          # a recurring, per-unit Price (per seat)
    billing_seat: str = "device"                # what a seat is: "device" or "user"
    # Per-seat price in cents, used only to display MRR on the operator dashboard.
    # Leave unset to hide dollar amounts (licenses/subscription counts still show).
    price_per_seat_cents: int | None = None

    # Email (SMTP) — INERT until host + user + password are set. Works with
    # Hostinger (smtp.hostinger.com:465 SSL, or :587 STARTTLS) or any SMTP host.
    # When unset: no email is sent, and registration OTP is skipped (open signup).
    smtp_host: str | None = None
    smtp_port: int = 465                # 465 = implicit SSL; anything else = STARTTLS
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None       # defaults to smtp_user when unset
    otp_ttl_minutes: int = 10
    password_reset_ttl_minutes: int = 60

    # Remediation blast-radius controls (per organization, rolling window). Above the
    # auto-approve burst, even 'automatic' actions require a human approval; above the
    # hard burst, new remediations are refused outright (fleet circuit breaker).
    remediation_burst_window_seconds: int = 300
    remediation_auto_approve_burst: int = 25
    remediation_hard_burst: int = 200

    # Security contact published at /.well-known/security.txt (RFC 9116).
    security_contact: str = "mailto:security@example.com"
    # Portal base URL Stripe Checkout/Portal redirect back to after payment.
    public_app_url: str = "http://localhost:3000"


def _ensure_database_url() -> None:
    """Railway's Postgres plugin exposes the connection string as DATABASE_URL.
    We expect ASTRA_DATABASE_URL (env_prefix). Bridge the two so either works,
    and fail with a clear, actionable message if neither is set."""
    astra_url = os.getenv("ASTRA_DATABASE_URL", "").strip()
    railway_url = os.getenv("DATABASE_URL", "").strip()

    if not astra_url and railway_url:
        os.environ["ASTRA_DATABASE_URL"] = railway_url
        astra_url = railway_url

    # Last resort: reconstruct from Railway's individual Postgres PG* variables
    # if they were referenced into this service (PGHOST/PGUSER/PGPASSWORD/...).
    if not astra_url:
        host = os.getenv("PGHOST") or os.getenv("POSTGRES_HOST")
        user = os.getenv("PGUSER") or os.getenv("POSTGRES_USER")
        password = os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD")
        db_name = os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB")
        port = os.getenv("PGPORT") or "5432"
        if host and user and password and db_name:
            astra_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
            os.environ["ASTRA_DATABASE_URL"] = astra_url
            print("[config] Reconstructed database URL from PG* environment variables")

    if not astra_url:
        # Diagnostic: prove exactly what env vars the container received (NAMES ONLY,
        # no values, so nothing secret is leaked). This tells us what Railway injected.
        all_keys = sorted(os.environ.keys())
        db_keys = [
            k for k in all_keys
            if any(t in k.upper() for t in ("DATA", "PG", "POSTGR", "SQL", "URL", "RAILWAY"))
        ]
        print("=" * 60)
        print("[config] FATAL: no database URL in container environment.")
        print(f"[config] DB/Railway-related env var NAMES present: {db_keys}")
        print(f"[config] TOTAL env vars present: {len(all_keys)}")
        print(f"[config] ALL env var NAMES: {all_keys}")
        print("=" * 60)
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
