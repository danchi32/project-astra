"""Test harness.

The environment is set before `app` is imported anywhere, because `get_settings()` is
lru_cached and `database.py` builds its engine at module import. Anything that imports the
app first gets the developer's real .env — which, for a service whose whole job is writing
to a lead database, is not a mistake worth risking.
"""
import os

# ── The suite must not touch the outside world ─────────────────────────────────
# `setdefault` and popping the environment were NOT enough, and the gap was expensive:
# pydantic-settings reads BOTH the process environment and the `.env` file, so once real
# credentials landed in `.env` the tests picked them up and started sending real Telegram
# alerts and real acknowledgement emails — to the addresses in the fixtures, one of which
# is a plausible real mailbox.
#
# Environment variables outrank the dotenv file, so setting these EXPLICITLY to empty is
# what actually disables them. `setdefault` cannot: the name is already absent from the
# environment, so it sets the test value, and the `.env` entry then wins anyway for every
# name the tests did not think to mention.
#
# Assigned before `app` is imported anywhere, because `get_settings()` is lru_cached and
# `database.py` builds its engine at module import.
os.environ["ASTRA_MKT_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ASTRA_MKT_INTAKE_SECRET"] = "test-intake-secret"
os.environ["ASTRA_MKT_ADMIN_TOKEN"] = "test-admin-token"

#: Every integration that can reach the network. Emptied explicitly, never merely omitted.
OUTBOUND_SETTINGS = (
    "ASTRA_MKT_N8N_LEAD_WEBHOOK_URL",
    "ASTRA_MKT_N8N_WEBHOOK_SECRET",
    "ASTRA_MKT_TELEGRAM_BOT_TOKEN",
    "ASTRA_MKT_TELEGRAM_CHAT_IDS",
    "ASTRA_MKT_ANTHROPIC_API_KEY",
    "ASTRA_MKT_RESEND_API_KEY",
    "ASTRA_MKT_SMTP_HOST",
    "ASTRA_MKT_SMTP_USER",
    "ASTRA_MKT_SMTP_PASSWORD",
    "ASTRA_MKT_BIGIN_CLIENT_ID",
    "ASTRA_MKT_BIGIN_CLIENT_SECRET",
    "ASTRA_MKT_BIGIN_REFRESH_TOKEN",
)
for _name in OUTBOUND_SETTINGS:
    os.environ[_name] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def session_factory():
    """A fresh in-memory database per test.

    StaticPool keeps every connection pointed at the same in-memory database; without it
    each checkout would get its own empty one and the schema created below would vanish.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def intake_secret() -> str:
    return os.environ["ASTRA_MKT_INTAKE_SECRET"]


@pytest.fixture
def admin_token() -> str:
    return os.environ["ASTRA_MKT_ADMIN_TOKEN"]


@pytest.fixture(autouse=True, scope="session")
def _no_outbound_integrations():
    """Fail the whole run if anything could reach the network.

    A belt to the environment's braces. The failure this guards against is silent by
    nature — a suite with live credentials still passes, it just also emails strangers —
    so it has to be checked rather than assumed.
    """
    from app.services.dispatch import LeadDispatcher
    from app.services.email import EmailService
    from app.services.scoring import LeadScorer
    from app.services.telegram import TelegramNotifier

    live = [
        name for name, enabled in (
            ("telegram", TelegramNotifier().enabled),
            ("email", EmailService().enabled),
            ("n8n dispatch", LeadDispatcher().enabled),
            ("model scoring", LeadScorer().model_enabled),
        ) if enabled
    ]
    if live:
        raise RuntimeError(
            "Tests would reach the network via: " + ", ".join(live) + ". "
            "conftest.py must empty every entry in OUTBOUND_SETTINGS before app import."
        )
