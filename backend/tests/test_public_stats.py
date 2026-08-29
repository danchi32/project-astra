"""The public stats endpoint.

It replaces four invented figures in the marketing homepage's hero. The tests that matter
are the ones about what it must NOT contain: it is served without authentication to
anyone who asks, and the operator's own workspace must never be counted as a customer.
"""
import pytest

from app.api.v1 import public as public_module


@pytest.fixture(autouse=True)
def _clear_stats_cache():
    """The endpoint caches for five minutes; tests must not read each other's answers."""
    public_module._stats_cache["value"] = None
    public_module._stats_cache["at"] = 0.0
    yield
    public_module._stats_cache["value"] = None
    public_module._stats_cache["at"] = 0.0


async def test_stats_are_public(client):
    """No token. The marketing site is a static export calling from a visitor's browser."""
    response = await client.get("/api/v1/public/stats")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "organizations", "devices", "devices_online", "remediations", "generated_at",
    }


async def test_stats_are_counts_and_nothing_else(client):
    """Anything identifying would be served to the whole internet.

    Names, hostnames, per-organisation rows: none of it belongs in a response that needs
    no credential. The schema is the guard, and this is the test that says so out loud.
    """
    body = (await client.get("/api/v1/public/stats")).json()

    for key, value in body.items():
        if key == "generated_at":
            continue
        assert isinstance(value, int), f"{key} is {type(value).__name__}, not a count"


async def test_counts_are_never_negative(client):
    body = (await client.get("/api/v1/public/stats")).json()
    assert body["organizations"] >= 0
    assert body["devices"] >= 0
    assert body["devices_online"] >= 0
    assert body["remediations"] >= 0


async def test_online_devices_cannot_exceed_total(client):
    """A homepage that says 12 of 8 devices are online is worse than one saying nothing."""
    body = (await client.get("/api/v1/public/stats")).json()
    assert body["devices_online"] <= body["devices"]


async def test_the_operators_own_organization_is_not_a_customer(session_factory, org):
    """The org containing a platform admin is our own workspace, not a customer.

    Counting it would put our own test organisation on the public homepage as a customer
    — a fabricated number of exactly the kind this endpoint exists to replace.
    """
    from sqlalchemy import func, select

    from app.core.security import hash_password
    from app.models import Organization, User, UserRole
    from app.services.platform import PlatformService

    async with session_factory() as session:
        internal = Organization(name="Technomate (internal)")
        session.add(internal)
        await session.flush()
        session.add(User(
            org_id=internal.id, email="operator@technomateai.com",
            full_name="Operator", hashed_password=hash_password("x"),
            role=UserRole.ADMIN, is_platform_admin=True,
        ))
        await session.commit()

        total = (await session.execute(
            select(func.count()).select_from(Organization)
        )).scalar_one()
        stats = await PlatformService(session).public_stats()

    assert total >= 2, "fixture did not create both organisations"
    assert stats.organizations == total - 1, (
        "the platform admin's own organisation is being counted as a customer"
    )


async def test_the_answer_is_cached(client, monkeypatch):
    """Every homepage visit calls this. Without a cache it is a database query per view."""
    calls = {"n": 0}
    from app.services.platform import PlatformService

    original = PlatformService.public_stats

    async def counted(self):
        calls["n"] += 1
        return await original(self)

    monkeypatch.setattr(PlatformService, "public_stats", counted)

    await client.get("/api/v1/public/stats")
    await client.get("/api/v1/public/stats")
    await client.get("/api/v1/public/stats")

    assert calls["n"] == 1, f"queried the database {calls['n']} times for three requests"
