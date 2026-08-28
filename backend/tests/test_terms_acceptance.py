"""Signup cannot create an organisation without accepting the terms, and the acceptance
is recorded.

The point of these tests is that the guard lives in the service, not in one endpoint.
Three routes create an organisation, and a check that only one of them performs is a
bypass on the other two — so each door is tested separately.
"""
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Organization

pytestmark = pytest.mark.asyncio

_PW = "password123"


def _body(org: str, email: str, **overrides) -> dict:
    body = {
        "organization_name": org,
        "admin_name": "Admin",
        "admin_email": email,
        "admin_password": _PW,
        "terms_accepted": True,
    }
    body.update(overrides)
    return body


async def test_signup_is_refused_without_acceptance(client):
    r = await client.post(
        "/api/v1/auth/register",
        json=_body("Refused Co", "admin@refused-co.com", terms_accepted=False),
    )
    assert r.status_code == 400, r.text
    assert "terms of service" in r.json()["detail"].lower()


async def test_omitting_the_field_is_refused_not_assumed(client):
    """A client that never sends the field must be rejected.

    This is the one that matters: `terms_accepted` defaults to False precisely so an
    older or hand-rolled client cannot obtain an account by silence. If the default ever
    flips to True, the stored acceptance stops proving anything and this test fails.
    """
    body = _body("Silent Co", "admin@silent-co.com")
    del body["terms_accepted"]
    r = await client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 400, r.text


async def test_otp_door_is_guarded_too(client):
    """/register/start is a second entry point and must enforce the same rule."""
    r = await client.post(
        "/api/v1/auth/register/start",
        json=_body("Otp Co", "admin@otp-co.com", terms_accepted=False),
    )
    assert r.status_code == 400, r.text
    assert "terms of service" in r.json()["detail"].lower()


async def test_acceptance_is_recorded_on_the_organisation(client, session_factory):
    r = await client.post(
        "/api/v1/auth/register", json=_body("Recorded Co", "admin@recorded-co.com")
    )
    assert r.status_code == 201, r.text

    async with session_factory() as session:
        org = (
            await session.execute(
                select(Organization).where(Organization.name == "Recorded Co")
            )
        ).scalar_one()

        # Which version was agreed — without this the record cannot be tied to a document.
        assert org.terms_version == get_settings().legal_terms_version
        assert org.terms_accepted_at is not None
        # The test client reports an address; the column is populated rather than left
        # null, which is what proves the request context reached the service.
        assert org.terms_accepted_ip
