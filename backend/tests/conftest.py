import os

# Must be set before any app import triggers Settings validation.
os.environ.setdefault("ASTRA_JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ASTRA_DATABASE_URL", "sqlite+aiosqlite://")
# Force the deterministic stub AI provider — tests must never call the real API,
# even if a developer has ASTRA_ANTHROPIC_API_KEY set in the environment or backend/.env.
os.environ["ASTRA_ANTHROPIC_API_KEY"] = ""
# Same reason, same hazard: a developer's backend/.env may point at a real MeshCentral
# relay, and a test that reached one would take over somebody's screen to prove a point.
# Forced empty here so the client reports itself unconfigured no matter what is on disk.
#
# EVERY relay setting belongs in this list. The cookie key was added to Settings after
# the first three and left out of here, and the gap was real: with a developer's key
# still readable, the suite could mint working viewer links for a live relay. A test
# caught it, which is luck — so the loop below covers whatever Settings declares rather
# than a list somebody has to remember to extend.
from app.core.config import Settings as _Settings

for _field, _info in _Settings.model_fields.items():
    if _field.startswith("meshcentral_"):
        # A flag's "off" is False, not the empty string — pydantic refuses to parse that
        # as a boolean and the whole suite fails to import.
        os.environ[f"ASTRA_{_field.upper()}"] = (
            "false" if _info.annotation is bool else ""
        )

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base, Organization, User, UserRole

ADMIN_PASSWORD = "AdminPassw0rd!234"
USER_PASSWORD = "UserPassw0rd!2345"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # The read-only gate middleware opens its own session via database.SessionLocal
    # (outside the dependency graph) — point it at the test DB too.
    import app.core.database as database

    original_session_local = database.SessionLocal
    database.SessionLocal = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    database.SessionLocal = original_session_local


@pytest_asyncio.fixture
async def org(session_factory) -> Organization:
    async with session_factory() as session:
        org = Organization(name="Acme Corp")
        session.add(org)
        await session.commit()
        return org


@pytest_asyncio.fixture
async def other_org(session_factory) -> Organization:
    async with session_factory() as session:
        org = Organization(name="Globex Inc")
        session.add(org)
        await session.commit()
        return org


async def _create_user(session_factory, org_id, email, password, role) -> User:
    async with session_factory() as session:
        user = User(
            org_id=org_id,
            email=email,
            full_name="Test Person",
            hashed_password=hash_password(password),
            role=role,
        )
        session.add(user)
        await session.commit()
        return user


@pytest_asyncio.fixture
async def admin_user(session_factory, org) -> User:
    return await _create_user(session_factory, org.id, "admin@acme.com", ADMIN_PASSWORD, UserRole.ADMIN)


@pytest_asyncio.fixture
async def regular_user(session_factory, org) -> User:
    return await _create_user(session_factory, org.id, "user@acme.com", USER_PASSWORD, UserRole.USER)


@pytest_asyncio.fixture
async def other_org_user(session_factory, other_org) -> User:
    return await _create_user(
        session_factory, other_org.id, "user@globex.com", USER_PASSWORD, UserRole.USER
    )


async def login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def auth_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    tokens = await login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(client, admin_user) -> dict[str, str]:
    return await auth_headers(client, admin_user.email, ADMIN_PASSWORD)


@pytest_asyncio.fixture
async def user_headers(client, regular_user) -> dict[str, str]:
    return await auth_headers(client, regular_user.email, USER_PASSWORD)
