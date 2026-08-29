from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for the ASTRA Marketing Service.

    The prefix is ASTRA_MKT_ rather than ASTRA_ on purpose. This service and the product
    backend read their environment from the same Secret Manager project and, during local
    work, often from the same shell. A shared prefix would let a stray ASTRA_DATABASE_URL
    point the marketing service at the customer database, which is the one mistake in this
    file that could not be undone.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASTRA_MKT_", extra="ignore")

    app_name: str = "ASTRA Marketing Service"
    environment: str = "development"
    log_level: str = "INFO"

    # No default — a marketing service pointed at nothing is better than one pointed at
    # the wrong database.
    database_url: str

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_async_driver(cls, value: str) -> str:
        """Make the string you copied out of the Neon console work unchanged.

        Two normalisations, both because Neon's connection string is written for libpq and
        we connect with asyncpg:

        * **Scheme.** Neon hands out `postgres://` or `postgresql://`; the async engine
          needs the asyncpg driver named explicitly. (Same rule as the product backend.)
        * **Query parameters.** Neon appends `?sslmode=require&channel_binding=require`.
          SQLAlchemy passes unknown query parameters straight through to
          `asyncpg.connect()`, which takes neither: `sslmode` is spelled `ssl` there, and
          `channel_binding` does not exist at all. Left alone, the first connection dies
          with `TypeError: connect() got an unexpected keyword argument 'sslmode'` — a
          failure that reads like a driver bug and is really a copy-paste artefact.

        Doing this here rather than telling an operator to hand-edit the URL means the
        obvious action (paste what Neon gave you) is also the correct one.
        """
        if not isinstance(value, str):
            return value

        if value.startswith("postgres://"):
            value = "postgresql+asyncpg://" + value[len("postgres://"):]
        elif value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://"):]

        if "+asyncpg://" not in value or "?" not in value:
            return value

        base, _, query = value.partition("?")
        kept: list[str] = []
        for param in query.split("&"):
            if not param:
                continue
            key, _, val = param.partition("=")
            key_lower = key.lower()
            if key_lower == "channel_binding":
                continue  # asyncpg has no such parameter
            if key_lower == "sslmode":
                # asyncpg's spelling. "require" is what Neon asks for and what we want:
                # never connect to a lead database in the clear.
                kept.append(f"ssl={val or 'require'}")
                continue
            kept.append(param)

        return f"{base}?{'&'.join(kept)}" if kept else base

    @property
    def migration_database_url(self) -> str:
        """The same database, reached over the DIRECT endpoint rather than the pooler.

        Neon's pooled hostname is the direct one with `-pooler` inserted after the
        endpoint id, so the direct form is derivable and does not need to be configured
        separately — which matters, because the obvious thing to copy out of the console
        is the pooled string, and it is the right one for the *app*.

        Migrations are the exception. PgBouncer's transaction pooling hands back a
        different backend between statements, so anything needing a stable session —
        which DDL and Alembic's own bookkeeping do — is unsafe on it. The product's
        migration to Neon learned this the expensive way with `pg_restore`; encoding it
        here means nobody has to remember it twice.
        """
        return self.database_url.replace("-pooler.", ".", 1)

    # ── Connection pool ────────────────────────────────────────────────────────
    # Neon scales compute to zero after ~5 minutes idle, and this service is idle far more
    # than the product API is — a marketing site gets a handful of leads a day. So
    # pre-ping is not a nicety here, it is the difference between the first lead of the
    # morning being stored and being lost.
    db_pool_size: int = 2
    db_max_overflow: int = 3
    db_pool_recycle_seconds: int = 300
    db_pool_pre_ping: bool = True

    # ── Lead intake ────────────────────────────────────────────────────────────
    #: Shared secret used to sign intake requests (see app/core/security.py). The website's
    #: contact.php holds the other copy. UNSET MEANS THE INTAKE ENDPOINT IS CLOSED: an
    #: unauthenticated public write endpoint is worse than no endpoint, so this one refuses
    #: rather than falling open. Every other integration in this service is inert when
    #: unconfigured; this one is *shut*.
    intake_secret: str = ""
    #: How far a signed request's timestamp may be from ours before it is treated as a
    #: replay. Generous enough for clock drift on shared hosting, short enough that a
    #: captured request is not reusable tomorrow.
    intake_max_skew_seconds: int = 300

    #: Bearer token for the read endpoints, which return names, emails and phone numbers.
    #: Same rule as `intake_secret`: UNSET MEANS CLOSED, not open. There is no scenario in
    #: which an unauthenticated lead list is the intended behaviour, so a missing token
    #: must not be the thing that produces one.
    admin_token: str = ""

    # ── Downstream fan-out (all inert until configured) ────────────────────────
    #: n8n webhook that runs enrichment, scoring, notification and CRM sync. The lead is
    #: already committed before this fires, so n8n being down costs a notification, never
    #: a lead — `dispatched_at` stays null and the replay job picks it up.
    n8n_lead_webhook_url: str = ""
    n8n_webhook_secret: str = ""

    #: Telegram approval/alert desk. Both must be set or the notifier stays silent.
    telegram_bot_token: str = ""
    #: Comma-separated numeric chat IDs allowed to receive alerts AND to act on them.
    #: An allowlist, not a single ID, so a second person can be added without a deploy.
    telegram_chat_ids: str = ""

    #: Anthropic key for lead scoring. Unset means the rules-only score is used, which is
    #: deliberately good enough to ship without it.
    anthropic_api_key: str = ""
    scoring_model: str = "claude-haiku-4-5"

    #: Zoho Bigin. Unset means leads are stored and alerted but not pushed to CRM.
    bigin_client_id: str = ""
    bigin_client_secret: str = ""
    bigin_refresh_token: str = ""
    #: Bigin is region-sharded; an India account is .in, not .com. Getting this wrong
    #: returns a confusing 401 rather than a redirect.
    bigin_api_domain: str = "https://www.zohoapis.in"
    bigin_accounts_domain: str = "https://accounts.zoho.in"

    #: The acknowledgement email. Resend's HTTPS API is tried first because it works on
    #: hosts that block outbound SMTP; SMTP is the fallback, and is what the existing
    #: Hostinger sales@ mailbox uses. Neither set means no acknowledgement is sent.
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "ASTRA <sales@technomateai.com>"
    booking_url: str = "https://cal.com/astraai/30min"
    site_url: str = "https://technomateai.com"

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Nothing in this service is called from a browser today — contact.php is server-side.
    # Kept empty on purpose so that adding a browser caller is a deliberate act.
    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
