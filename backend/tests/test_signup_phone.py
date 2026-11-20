"""Signup requires a phone number, normalised to E.164 and kept on the organisation.

Both doors are tested: direct /register, and /register/start -> /register/verify, where
the number has to survive the pending row in between.
"""
import re

import pytest
from pydantic import ValidationError
from sqlalchemy import select

import app.services.email as email_mod
from app.models import Organization, User
from app.schemas.auth import RegisterRequest

pytestmark = pytest.mark.asyncio


def _body(org: str, email: str, **overrides) -> dict:
    body = {"organization_name": org, "admin_name": "Admin", "admin_email": email,
            "admin_password": "password123", "terms_accepted": True,
            "phone": "+91 85954 92500"}
    body.update(overrides)
    return body


@pytest.mark.parametrize("raw, stored", [
    ("+91 85954 92500", "+918595492500"),
    ("+918595492500", "+918595492500"),
    ("0091-85954-92500", "+918595492500"),
    ("+1 (415) 555-0132", "+14155550132"),
    ("+44 20.7946.0958", "+442079460958"),
])
async def test_accepted_phones_are_normalised(raw, stored):
    assert RegisterRequest(**_body("Co", "a@co-x.com", phone=raw)).phone == stored


@pytest.mark.parametrize("raw", [
    "85954 92500",          # no country code
    "+0 85954 92500",       # country codes never start with 0
    "+91 8595 4925 0012 34",  # 16 digits, past E.164's 15
    "+12345",               # too short to be a number
    "+91 85954 9250O",      # letter O, not zero
    "",
])
async def test_rejected_phones(raw):
    with pytest.raises(ValidationError, match="country code"):
        RegisterRequest(**_body("Co", "a@co-x.com", phone=raw))


async def test_signup_without_phone_is_422(client):
    body = _body("No Phone Co", "admin@no-phone-co.com")
    del body["phone"]
    r = await client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 422, r.text
    assert any(e["loc"][-1] == "phone" for e in r.json()["detail"])


async def test_signup_with_invalid_phone_is_422(client):
    r = await client.post("/api/v1/auth/register/start",
                          json=_body("Bad Phone Co", "admin@bad-phone-co.com", phone="12345"))
    assert r.status_code == 422, r.text
    assert "country code" in r.text


async def test_direct_signup_stores_phone(client, session_factory):
    r = await client.post("/api/v1/auth/register", json=_body("Phone Co", "admin@phone-co.com"))
    assert r.status_code == 201, r.text
    async with session_factory() as s:
        org = (await s.execute(select(Organization).where(Organization.name == "Phone Co"))).scalar_one()
    assert org.contact_phone == "+918595492500"


async def test_otp_signup_carries_phone_through_pending(client, session_factory, monkeypatch):
    monkeypatch.setattr(email_mod.settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(email_mod.settings, "smtp_user", "noreply@test.com")
    monkeypatch.setattr(email_mod.settings, "smtp_password", "pw")
    sent: list = []
    monkeypatch.setattr(email_mod.EmailService, "_deliver", lambda self, msg: sent.append(msg))

    r = await client.post("/api/v1/auth/register/start",
                          json=_body("Otp Phone Co", "admin@otp-phone-co.com", phone="+1 415 555 0132"))
    assert r.json()["otp_required"] is True, r.text
    code = re.search(r"(\d{6})", sent[0].as_string()).group(1)
    r = await client.post("/api/v1/auth/register/verify",
                          json={"admin_email": "admin@otp-phone-co.com", "code": code})
    assert r.status_code == 201, r.text
    async with session_factory() as s:
        org = (await s.execute(select(Organization).where(Organization.name == "Otp Phone Co"))).scalar_one()
    assert org.contact_phone == "+14155550132"


async def test_platform_console_shows_and_finds_phone(client, session_factory):
    op = await client.post("/api/v1/auth/register", json=_body("Op Co", "op@op-co.com"))
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == "op@op-co.com"))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    headers = {"Authorization": f"Bearer {op.json()['access_token']}"}
    await client.post("/api/v1/auth/register",
                      json=_body("Lead Co", "admin@lead-co.com", phone="+1 415 555 0132"))

    r = await client.get("/api/v1/platform/organizations", headers=headers,
                         params={"q": "+1 415 555"})
    assert r.status_code == 200, r.text
    assert [(o["name"], o["contact_phone"]) for o in r.json()["items"]] == [("Lead Co", "+14155550132")]
