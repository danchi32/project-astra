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

    # ── Connection pool ────────────────────────────────────────────────────────
    # Env-driven because the right values differ per platform: a single-instance PaaS
    # can hold a big pool, while N Cloud Run instances each hold their own — so the
    # total against Postgres is pool × instances and must stay under its limit.
    # (Neon's pooled endpoint fronts PgBouncer, which absorbs a lot of this.)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    # Recycle connections before a proxy/server silently drops them. Neon's pooler and
    # most managed providers cut idle connections after a few minutes.
    db_pool_recycle_seconds: int = 300
    # Check a connection is alive before handing it out. REQUIRED on Neon: it scales the
    # compute to zero after ~5 min idle and restarts weekly for updates, so pooled
    # connections go dead and the next request would otherwise fail.
    db_pool_pre_ping: bool = True

    # ── Telemetry retention ────────────────────────────────────────────────────
    # Raw snapshots arrive ~1/device/minute and are only ever read as "the latest" or
    # "the last 60", so they are pruned per device on ingest. Long-range history is
    # preserved in telemetry_daily_rollups, which is never pruned.
    # 0 disables pruning (keeps every row).
    telemetry_retention_days: int = 7
    # Floor: never prune a device below its newest N snapshots, however old they are.
    # Matches the largest read (`get_snapshots(limit=60)`) so the charts always have data,
    # and protects devices that return from a long offline spell with only stale buffered
    # telemetry.
    telemetry_keep_min_snapshots: int = 60

    # ── Agent rate limiting ────────────────────────────────────────────────────
    # A healthy agent makes ~6 requests/min (heartbeat + telemetry + two remediation
    # pollers), so 120/min is ~20x headroom — it should only ever catch a stuck retry
    # loop. Starts in LOG-ONLY mode: breaches are logged but never rejected, because a
    # too-tight limit would drop real heartbeats and show devices as offline. Watch the
    # logs against live fleet traffic, then set ASTRA_AGENT_RATE_LIMIT_ENFORCE=true.
    agent_rate_limit_enabled: bool = True
    agent_rate_limit_enforce: bool = False
    agent_rate_limit_requests: int = 120
    agent_rate_limit_window_seconds: int = 60

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]

    # The marketing site is a static export on shared hosting: it has no server of its own
    # to proxy through, so its chat widget calls this API straight from the browser and
    # needs its origin allowed. Kept apart from `cors_origins` (which is the portal's, and
    # is set per environment) so that adding a preview URL for the portal cannot silently
    # drop the public site, and so the default works in production without a deploy-time
    # env var — a comma inside a JSON array does not survive `gcloud --set-env-vars`.
    marketing_origins: list[str] = [
        "https://technomateai.com",
        "https://www.technomateai.com",
        "http://localhost:3200",  # `npm run dev` in website/
    ]

    # The website chatbot is open to anyone, and every question it cannot answer from the
    # FAQ alone costs a model call. 12 questions per 10 minutes per IP is more than a real
    # pre-sales conversation needs and far less than a script would want. ENFORCED, unlike
    # the agent limiter above: there is no heartbeat to lose here, only spend.
    public_assistant_rate_limit_requests: int = 12
    public_assistant_rate_limit_window_seconds: int = 600

    # Self-service signup is for organisations, so a personal/free/disposable provider
    # (gmail, outlook, mailinator…) is rejected — see app/core/email_domains.py. Kept as a
    # switch rather than hardcoded: a genuine small-business prospect on a personal address
    # is a sales conversation, not a bug, and an operator can also provision them directly
    # via the platform console, which is not subject to this rule.
    require_work_email: bool = True

    # Public base URL of this backend as reached by Windows agents. Baked into the
    # generated agent installer as the default ServerUrl; the portal can override it.
    # Production: set ASTRA_PUBLIC_API_URL to the custom domain, e.g.
    #   https://api.astra.technomateai.com
    # Prefer a domain you own over the platform hostname (*.up.railway.app):
    # filtering resolvers commonly block cloud-hosting subdomains outright, which is
    # what forces the agent's hosts-file workaround below.
    public_api_url: str = "http://localhost:8000"

    # Optional IP that the portable agent installer pins public_api_url's hostname to
    # in the endpoint's hosts file, for networks whose DNS cannot resolve it.
    #
    # EMPTY BY DEFAULT, and it should stay empty when public_api_url is a custom
    # domain you control. A hosts pin OVERRIDES working DNS, so a stale one
    # blackholes the agent permanently once the IP changes (platform edge IPs
    # rotate). Only set ASTRA_AGENT_BACKEND_IP as a temporary workaround, and
    # clear it once DNS resolves.
    agent_backend_ip: str = ""

    # Root log level. INFO because the records this codebase already writes are the ones
    # worth having when something goes wrong in production; raise it to WARNING if the
    # volume ever becomes the problem.
    log_level: str = "INFO"

    # AI engine — when the API key is unset, a deterministic stub provider is used
    # (local demo + tests run without a key or network).
    anthropic_api_key: str | None = None
    ai_model: str = "claude-sonnet-5"
    # Sonnet 5 thinks by default — leaving the thinking parameter unset gets adaptive
    # thinking, where on the previous model it got none. max_tokens caps thinking AND the
    # reply together, so a budget sized for reply-only would now cut answers off mid
    # sentence. Raised to leave the reasoning somewhere to go.
    ai_max_tokens: int = 8192
    ai_max_tool_iterations: int = 6

    # Cost controls — an intent gate rejects off-topic queries before any LLM call,
    # and a semantic cache serves repeated questions from stored answers (no LLM call).
    ai_intent_gate_enabled: bool = True
    ai_cache_enabled: bool = True
    ai_cache_similarity_threshold: float = 0.85

    # Embeddings — "auto" uses Voyage when a key is present and the offline hashing
    # provider otherwise; "voyage" refuses to start without a key rather than silently
    # writing incompatible vectors. Anthropic has no embeddings endpoint, which is why
    # this is a separate provider from the AI key above.
    # Switching provider or model changes the vector space: existing rows keep working
    # (search filters to the current model) but stay unfindable until re-embedded —
    # scripts/reembed.py does that.
    embedding_provider: str = "auto"
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-4-lite"

    # Encrypts third-party credentials organizations give us (helpdesk API keys). A
    # Fernet key — generate with app.core.crypto.generate_key(). Unset means those
    # integrations stay off rather than storing secrets in the clear.
    # Rotating this makes existing stored credentials undecryptable: they must be
    # re-entered, so treat it as long-lived.
    secrets_key: str | None = None

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

    @field_validator("price_per_seat_cents", mode="before")
    @classmethod
    def _coerce_price_cents(cls, value):
        """Tolerate a mistyped price variable (e.g. '$8', '8.00', '') — a display-only
        setting must NEVER crash the whole backend on boot. It's a whole number of cents;
        anything else disables pricing (dashboard shows '—') with a warning, rather than
        aborting startup. Use e.g. 800 for $8.00/seat."""
        if value is None or isinstance(value, int):
            return value
        s = str(value).strip()
        if s == "":
            return None
        if s.lstrip("+-").isdigit():
            return int(s)
        import sys
        print(
            f"[config] WARNING: ASTRA_PRICE_PER_SEAT_CENTS={value!r} is not a whole number "
            f"of cents — pricing left unset. Use an integer, e.g. 800 for $8.00/seat.",
            file=sys.stderr,
        )
        return None

    # Email (SMTP) — INERT until host + user + password are set. Works with
    # Hostinger (smtp.hostinger.com:465 SSL, or :587 STARTTLS) or any SMTP host.
    # When unset: no email is sent, and registration OTP is skipped (open signup).
    # -- Payment rails (each INERT until its keys are set) ---------------------
    # Razorpay: Indian customers (UPI / cards / netbanking / e-mandate, INR).
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_plan_id: str | None = None          # a per-seat recurring plan (INR)
    razorpay_webhook_secret: str | None = None

    # Paddle: international customers (Merchant of Record — handles global VAT).
    paddle_api_key: str | None = None
    paddle_price_id: str | None = None           # a per-seat recurring price
    paddle_webhook_secret: str | None = None
    paddle_sandbox: bool = True                  # use Paddle's sandbox API host

    # PayPal: international customers (cross-border only — PayPal cannot process
    # domestic Indian payments). Unlike Paddle it is NOT a merchant of record, so
    # tax compliance stays with us.
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_plan_id: str | None = None            # a per-seat recurring billing plan
    paypal_webhook_id: str | None = None         # needed to verify webhook signatures
    paypal_sandbox: bool = True                  # use PayPal's sandbox API host

    # Preferred transport on platforms that block SMTP (e.g. Railway): Resend's
    # HTTPS API. When set, it's used instead of SMTP. Verify your domain in Resend.
    resend_api_key: str | None = None

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

    # Agent auto-update channel. The backend only RELAYS the already-signed manifest it
    # fetches from these URLs (e.g. a GitHub Releases "latest/download" asset); it never
    # signs anything. Agents verify the signature against a key pinned in their binary, so a
    # compromise of this backend cannot forge an update. Both must be set for the feature to
    # be active; otherwise /agent/update reports no update available.
    agent_update_manifest_url: str | None = None    # raw signed manifest JSON
    agent_update_signature_url: str | None = None    # base64 RSA-SHA256 signature of that JSON
    agent_update_cache_seconds: int = 300
    # Cap how long a cached manifest may be served after the upstream goes unreachable, so a
    # transient outage can't cause an indefinitely stale (rollback-adjacent) manifest to persist.
    agent_update_max_stale_seconds: int = 86400

    # Security contact published at /.well-known/security.txt (RFC 9116).
    security_contact: str = "mailto:security@example.com"
    # Portal base URL that payment rails and email links redirect back to. Stored as the
    # ORIGIN only — redirects append their own path (/billing, /reset-password, …).
    public_app_url: str = "http://localhost:3000"

    @field_validator("public_app_url", mode="before")
    @classmethod
    def _origin_only(cls, value):
        """Keep only scheme://host. Tolerates a pasted full URL like
        'https://astra.technomateai.com/login' — otherwise appending '/billing' would produce
        a broken '/login/billing' redirect (404 after a PayPal cancel/return)."""
        if not value or not isinstance(value, str):
            return value
        from urllib.parse import urlparse
        parsed = urlparse(value.strip())
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return value.strip().rstrip("/")


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
