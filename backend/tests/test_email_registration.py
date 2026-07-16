"""Email foundation + registration OTP (verify-before-create).

SMTP delivery is monkeypatched — no real emails. Verifies: inert when unconfigured,
direct signup when email is off, and the OTP two-step when email is on.
"""
import re

from sqlalchemy import select

import app.services.email as email_mod
from app.models import PendingRegistration, User

_PW = "Password12345"


def _enable_email(monkeypatch) -> list:
    """Turn email 'on' and capture every delivered message instead of sending it."""
    monkeypatch.setattr(email_mod.settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(email_mod.settings, "smtp_user", "noreply@test.com")
    monkeypatch.setattr(email_mod.settings, "smtp_password", "pw")
    sent: list = []
    monkeypatch.setattr(email_mod.EmailService, "_deliver", lambda self, msg: sent.append(msg))
    return sent


def _code(msg) -> str:
    return re.search(r"(\d{6})", msg.as_string()).group(1)


async def _start(client, org="OTP Co", email="otp@co.com"):
    return await client.post("/api/v1/auth/register/start", json={
        "organization_name": org, "admin_name": "A", "admin_email": email, "admin_password": _PW})


async def test_email_service_inert_by_default(client):
    svc = email_mod.EmailService()
    assert svc.enabled is False
    assert await svc.send(to="x@y.com", subject="s", html="<p>h</p>") is False


async def test_resend_transport_preferred_when_key_set(monkeypatch):
    monkeypatch.setattr(email_mod.settings, "resend_api_key", "re_test")
    calls: list = []

    async def fake_resend(self, *, to, subject, html, text):
        calls.append((to, subject))
        return True

    monkeypatch.setattr(email_mod.EmailService, "_send_resend", fake_resend)
    svc = email_mod.EmailService()
    assert svc.enabled is True  # a Resend key alone enables email (no SMTP needed)
    assert await svc.send(to="x@y.com", subject="hi", html="<p>h</p>") is True
    assert calls == [("x@y.com", "hi")]


async def test_register_start_direct_when_email_disabled(client, session_factory):
    r = await _start(client, email="direct@co.com")
    assert r.status_code == 200, r.text
    assert r.json()["otp_required"] is False
    assert r.json()["access_token"]  # created immediately
    async with session_factory() as s:
        assert (await s.execute(select(User).where(User.email == "direct@co.com"))).scalar_one_or_none() is not None


async def test_register_start_emails_otp_and_creates_nothing_yet(client, session_factory, monkeypatch):
    sent = _enable_email(monkeypatch)
    r = await _start(client, org="Pending Co", email="pending@co.com")
    assert r.status_code == 200, r.text
    assert r.json()["otp_required"] is True
    assert r.json()["access_token"] is None
    assert len(sent) == 1  # the OTP email
    async with session_factory() as s:
        assert (await s.execute(select(User).where(User.email == "pending@co.com"))).scalar_one_or_none() is None
        assert (await s.execute(select(PendingRegistration).where(PendingRegistration.email == "pending@co.com"))).scalar_one_or_none() is not None


async def test_register_verify_creates_org_and_sends_welcome(client, monkeypatch):
    sent = _enable_email(monkeypatch)
    await _start(client, org="Verify Co", email="v@co.com")
    code = _code(sent[0])

    r = await client.post("/api/v1/auth/register/verify", json={"admin_email": "v@co.com", "code": code})
    assert r.status_code == 201, r.text
    assert r.json()["access_token"]
    assert len(sent) == 2  # OTP + welcome

    login = await client.post("/api/v1/auth/login", json={"email": "v@co.com", "password": _PW})
    assert login.status_code == 200


async def test_register_verify_rejects_wrong_code(client, session_factory, monkeypatch):
    sent = _enable_email(monkeypatch)
    await _start(client, org="Wrong Co", email="w@co.com")
    real = _code(sent[0])
    wrong = "111111" if real != "111111" else "222222"

    r = await client.post("/api/v1/auth/register/verify", json={"admin_email": "w@co.com", "code": wrong})
    assert r.status_code == 400
    async with session_factory() as s:
        assert (await s.execute(select(User).where(User.email == "w@co.com"))).scalar_one_or_none() is None
