import os

# Must be set before any app import triggers Settings validation.
os.environ.setdefault("ASTRA_JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ASTRA_DATABASE_URL", "sqlite+aiosqlite://")
# Force the deterministic stub AI provider — tests must never call the real API,
# even if a developer has ASTRA_ANTHROPIC_API_KEY set in the environment or backend/.env.
os.environ["ASTRA_ANTHROPIC_API_KEY"] = ""

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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


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
