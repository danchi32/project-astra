"""Self-service signup rules: a work email is required (personal/free/disposable providers
are rejected), one organisation per corporate email domain, and the 8-character password
floor."""

import pytest

from app.core.config import get_settings
from app.core.email_domains import corporate_domain, is_free_email_domain


def _body(org, email, pw="password123", terms=True):
    return {"organization_name": org, "admin_name": "Admin", "admin_email": email,
            "admin_password": pw, "terms_accepted": terms}


async def _register(client, org, email, pw="password123"):
    return await client.post("/api/v1/auth/register", json=_body(org, email, pw))


def test_corporate_domain_helper():
    assert corporate_domain("a@acme.com") == "acme.com"
    assert corporate_domain("A@ACME.COM") == "acme.com"       # case-insensitive
    assert corporate_domain("x@gmail.com") is None            # personal -> exempt
    assert corporate_domain("x@outlook.com") is None
    assert corporate_domain("") is None


async def test_second_signup_from_same_corporate_domain_is_blocked(client):
    first = await _register(client, "Acme Inc", "founder@acme-corp.com")
    assert first.status_code == 201, first.text

    second = await _register(client, "Acme Two", "another@acme-corp.com")
    assert second.status_code == 409, second.text
    assert "already registered" in second.json()["detail"].lower()
    assert "acme-corp.com" in second.json()["detail"]


def test_is_free_email_domain_helper():
    assert is_free_email_domain("x@gmail.com")
    assert is_free_email_domain("X@GMAIL.COM")            # case-insensitive
    assert is_free_email_domain("x@mailinator.com")       # disposable counts too
    assert not is_free_email_domain("x@acme-corp.com")
    assert not is_free_email_domain("")


@pytest.mark.parametrize("email", [
    "alice@gmail.com",
    "bob@outlook.com",
    "carol@yahoo.co.in",
    "dave@icloud.com",
    "eve@mailinator.com",      # disposable
])
async def test_personal_and_disposable_domains_are_rejected(client, email):
    r = await _register(client, "Personal Co", email)
    assert r.status_code == 400, r.text
    assert "work email" in r.json()["detail"].lower()


async def test_work_email_requirement_can_be_relaxed(client, monkeypatch):
    """The rule is a switch, not a hardcode — a small-business prospect on a personal
    address is a sales decision, so it must be possible to let them through."""
    monkeypatch.setattr(get_settings(), "require_work_email", False)
    r = await _register(client, "Personal Co", "alice@gmail.com")
    assert r.status_code == 201, r.text


async def test_otp_signup_path_is_gated_too(client):
    """Both signup doors enforce it — the emailed-code flow must not be a way around the
    rule (it's a separate entry point that also calls the guard)."""
    blocked = await client.post("/api/v1/auth/register/start", json={
        "organization_name": "Personal Co", "admin_name": "A",
        "admin_email": "alice@gmail.com", "admin_password": "password123",
        "terms_accepted": True})
    assert blocked.status_code == 400, blocked.text
    assert "work email" in blocked.json()["detail"].lower()

    allowed = await client.post("/api/v1/auth/register/start", json={
        "organization_name": "Work Co", "admin_name": "A",
        "admin_email": "admin@work-co.com", "admin_password": "password123",
        "terms_accepted": True})
    assert allowed.status_code in (200, 201, 202), allowed.text


async def test_password_floor_is_eight(client):
    ok = await _register(client, "Eight Co", "admin@eight-co.com", pw="abcd1234")   # 8 chars
    assert ok.status_code == 201, ok.text

    too_short = await _register(client, "Seven Co", "admin@seven-co.com", pw="abc1234")  # 7
    assert too_short.status_code == 422   # pydantic min_length rejects before the service
