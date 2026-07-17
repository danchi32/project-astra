"""Payment rails: Razorpay (India) + Paddle (international).

Webhook signing is the security boundary here — a forged webhook could mark an org
as paid. These tests verify signature checking and lifecycle mapping. No network.
"""
import hashlib
import hmac
import json
import uuid

import pytest

import app.services.payments.paddle_provider as paddle_mod
import app.services.payments.razorpay_provider as razorpay_mod
from app.models import SubscriptionStatus
from app.services.exceptions import ValidationError
from app.services.payments import PaddleProvider, RazorpayProvider, available_providers, get_provider

_ORG = uuid.uuid4()


def test_both_rails_inert_by_default():
    assert RazorpayProvider().enabled is False
    assert RazorpayProvider().can_checkout is False
    assert PaddleProvider().enabled is False
    assert PaddleProvider().can_checkout is False
    assert available_providers() == []          # nothing configured -> nothing sells


def test_get_provider_resolves_by_name():
    assert get_provider("razorpay").name == "razorpay"
    assert get_provider("paddle").name == "paddle"
    assert get_provider("stripe") is None
    assert get_provider(None) is None


# -- Razorpay -----------------------------------------------------------------

def _razorpay_body(status="active", quantity=5) -> bytes:
    return json.dumps({
        "event": f"subscription.{status}",
        "payload": {"subscription": {"entity": {
            "id": "sub_RZP1", "status": status, "quantity": quantity,
            "current_end": 1893456000, "customer_id": "cust_1",
            "notes": {"org_id": str(_ORG)},
        }}},
    }).encode()


def _razorpay_sig(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_razorpay_webhook_valid_signature(monkeypatch):
    monkeypatch.setattr(razorpay_mod.settings, "razorpay_webhook_secret", "whsec_rzp")
    body = _razorpay_body()
    ev = RazorpayProvider().parse_webhook(
        payload=body, headers={"x-razorpay-signature": _razorpay_sig(body, "whsec_rzp")}
    )
    assert ev.ignored is False
    assert ev.org_id == _ORG
    assert ev.subscription_id == "sub_RZP1"
    assert ev.status is SubscriptionStatus.ACTIVE
    assert ev.quantity == 5
    assert ev.period_end is not None


def test_razorpay_webhook_rejects_forged_signature(monkeypatch):
    monkeypatch.setattr(razorpay_mod.settings, "razorpay_webhook_secret", "whsec_rzp")
    with pytest.raises(ValidationError):
        RazorpayProvider().parse_webhook(
            payload=_razorpay_body(), headers={"x-razorpay-signature": "deadbeef"}
        )


@pytest.mark.parametrize("rzp_status,expected", [
    ("active", SubscriptionStatus.ACTIVE),
    ("halted", SubscriptionStatus.PAST_DUE),     # retries exhausted -> read-only
    ("pending", SubscriptionStatus.PAST_DUE),
    ("cancelled", SubscriptionStatus.CANCELED),
])
def test_razorpay_status_mapping(monkeypatch, rzp_status, expected):
    monkeypatch.setattr(razorpay_mod.settings, "razorpay_webhook_secret", "s")
    body = _razorpay_body(status=rzp_status)
    ev = RazorpayProvider().parse_webhook(
        payload=body, headers={"x-razorpay-signature": _razorpay_sig(body, "s")}
    )
    assert ev.status is expected


# -- Paddle -------------------------------------------------------------------

def _paddle_body(status="active", quantity=3) -> bytes:
    return json.dumps({
        "event_type": "subscription.activated",
        "data": {
            "id": "sub_PDL1", "status": status, "customer_id": "ctm_1",
            "items": [{"quantity": quantity}],
            "custom_data": {"org_id": str(_ORG)},
            "current_billing_period": {"ends_at": "2026-08-01T10:00:00.000Z"},
        },
    }).encode()


def _paddle_headers(body: bytes, secret: str, ts: str = "1700000000") -> dict:
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return {"paddle-signature": f"ts={ts};h1={h1}"}


def test_paddle_webhook_valid_signature(monkeypatch):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "whsec_pdl")
    body = _paddle_body()
    ev = PaddleProvider().parse_webhook(payload=body, headers=_paddle_headers(body, "whsec_pdl"))
    assert ev.ignored is False
    assert ev.org_id == _ORG
    assert ev.subscription_id == "sub_PDL1"
    assert ev.customer_id == "ctm_1"
    assert ev.status is SubscriptionStatus.ACTIVE
    assert ev.quantity == 3
    assert ev.period_end is not None and ev.period_end.year == 2026


def test_paddle_webhook_rejects_forged_signature(monkeypatch):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "whsec_pdl")
    body = _paddle_body()
    with pytest.raises(ValidationError):
        PaddleProvider().parse_webhook(
            payload=body, headers={"paddle-signature": "ts=1700000000;h1=deadbeef"}
        )


def test_paddle_webhook_rejects_malformed_signature_header(monkeypatch):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "whsec_pdl")
    with pytest.raises(ValidationError):
        PaddleProvider().parse_webhook(payload=_paddle_body(), headers={"paddle-signature": "junk"})


@pytest.mark.parametrize("pdl_status,expected", [
    ("active", SubscriptionStatus.ACTIVE),
    ("trialing", SubscriptionStatus.ACTIVE),
    ("past_due", SubscriptionStatus.PAST_DUE),
    ("paused", SubscriptionStatus.SUSPENDED),
    ("canceled", SubscriptionStatus.CANCELED),
])
def test_paddle_status_mapping(monkeypatch, pdl_status, expected):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "s")
    body = _paddle_body(status=pdl_status)
    ev = PaddleProvider().parse_webhook(payload=body, headers=_paddle_headers(body, "s"))
    assert ev.status is expected


def test_paddle_ignores_non_subscription_events(monkeypatch):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "s")
    body = json.dumps({"event_type": "transaction.created", "data": {}}).encode()
    ev = PaddleProvider().parse_webhook(payload=body, headers=_paddle_headers(body, "s"))
    assert ev.ignored is True


# -- endpoint integration (the URL you give Paddle/Razorpay) -------------------

async def _register_org(client, session_factory, name, email):
    from sqlalchemy import select

    from app.models import Organization
    from app.services.invites import InviteService

    async with session_factory() as s:
        _, code = await InviteService(s).create(note="t", expires_in_days=30)
    r = await client.post("/api/v1/auth/register", json={
        "invite_code": code, "organization_name": name, "admin_name": "A",
        "admin_email": email, "admin_password": "Password12345",
    })
    assert r.status_code == 201, r.text
    async with session_factory() as s:
        return (await s.execute(select(Organization).where(Organization.name == name))).scalar_one()


async def test_paddle_webhook_endpoint_activates_org_and_sets_licenses(
    client, session_factory, monkeypatch
):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "whsec_pdl")
    org = await _register_org(client, session_factory, "Paddle Co", "p@paddle.com")

    body = json.dumps({
        "event_type": "subscription.activated",
        "data": {
            "id": "sub_LIVE", "status": "active", "customer_id": "ctm_9",
            "items": [{"quantity": 12}],
            "custom_data": {"org_id": str(org.id)},
            "current_billing_period": {"ends_at": "2026-09-01T10:00:00.000Z"},
        },
    }).encode()

    r = await client.post(
        "/api/v1/billing/webhook/paddle", content=body, headers=_paddle_headers(body, "whsec_pdl")
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True

    from sqlalchemy import select

    from app.models import Organization
    async with session_factory() as s:
        fresh = (await s.execute(select(Organization).where(Organization.id == org.id))).scalar_one()
    assert fresh.subscription_status is SubscriptionStatus.ACTIVE
    assert fresh.license_count == 12                  # licenses come from the rail
    assert fresh.provider_subscription_id == "sub_LIVE"
    assert fresh.provider_customer_id == "ctm_9"
    assert fresh.current_period_end is not None


async def test_paddle_webhook_endpoint_rejects_forged_signature(client, session_factory, monkeypatch):
    monkeypatch.setattr(paddle_mod.settings, "paddle_webhook_secret", "whsec_pdl")
    body = _paddle_body()
    r = await client.post(
        "/api/v1/billing/webhook/paddle",
        content=body,
        headers={"paddle-signature": "ts=1700000000;h1=deadbeef"},
    )
    assert r.status_code == 400  # forged webhook can never mark an org paid
