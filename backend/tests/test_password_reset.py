"""Password reset ('forgot password') over email. SMTP delivery is monkeypatched."""
import re

from sqlalchemy import select

import app.services.email as email_mod
from app.models import PasswordResetToken

_PW = "Password12345"
_NEW = "BrandNewPass99!"


def _enable_email(monkeypatch) -> list:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(email_mod.settings, "smtp_user", "noreply@test.com")
    monkeypatch.setattr(email_mod.settings, "smtp_password", "pw")
    monkeypatch.setattr(email_mod.settings, "public_app_url", "https://portal.test")
    sent: list = []
    monkeypatch.setattr(email_mod.EmailService, "_deliver", lambda self, msg: sent.append(msg))
    return sent


def _token_from(msg) -> str:
    # Decode the message body (quoted-printable soft-wraps would otherwise split
    # the long token across lines).
    text = ""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            text = part.get_content()
            break
    return re.search(r"reset-password\?token=([A-Za-z0-9_-]+)", text).group(1)


async def test_reset_request_is_silent_and_noop_when_email_off(client, admin_user):
    # No email configured → request still returns 200 and does nothing.
    r = await client.post("/api/v1/auth/password-reset/request", json={"email": admin_user.email})
    assert r.status_code == 200


async def test_reset_request_unknown_email_does_not_leak(client, monkeypatch):
    _enable_email(monkeypatch)
    r = await client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200  # same response as a real account — no enumeration


async def test_full_reset_flow(client, session_factory, admin_user, monkeypatch):
    sent = _enable_email(monkeypatch)
    req = await client.post("/api/v1/auth/password-reset/request", json={"email": admin_user.email})
    assert req.status_code == 200
    assert len(sent) == 1
    token = _token_from(sent[0])

    confirm = await client.post("/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": _NEW})
    assert confirm.status_code == 200

    # Old password no longer works; new one does.
    assert (await client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": _PW})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": _NEW})).status_code == 200

    # A "password changed" confirmation email was also sent.
    assert len(sent) == 2


async def test_reset_token_is_single_use(client, session_factory, admin_user, monkeypatch):
    sent = _enable_email(monkeypatch)
    await client.post("/api/v1/auth/password-reset/request", json={"email": admin_user.email})
    token = _token_from(sent[0])

    first = await client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": _NEW})
    assert first.status_code == 200
    second = await client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "AnotherOne123"})
    assert second.status_code == 400  # already used


async def test_reset_rejects_bad_token(client, monkeypatch):
    _enable_email(monkeypatch)
    r = await client.post("/api/v1/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": _NEW})
    assert r.status_code == 400


async def test_reset_requests_keep_only_newest_token(client, session_factory, admin_user, monkeypatch):
    sent = _enable_email(monkeypatch)
    await client.post("/api/v1/auth/password-reset/request", json={"email": admin_user.email})
    await client.post("/api/v1/auth/password-reset/request", json={"email": admin_user.email})
    # Only one live token per user.
    async with session_factory() as s:
        rows = (await s.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == admin_user.id))).scalars().all()
    assert len(rows) == 1
    # The first (older) token no longer works; the newest does.
    old = _token_from(sent[0])
    assert (await client.post("/api/v1/auth/password-reset/confirm", json={"token": old, "new_password": _NEW})).status_code == 400
