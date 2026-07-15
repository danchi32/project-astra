"""Phase B: per-seat Stripe billing.

Stripe network calls are monkeypatched — these tests verify our own logic:
inert-until-configured, seat counting, and webhook-driven subscription state
feeding the read-only gate. No real Stripe calls, no keys needed.
"""
import stripe
from sqlalchemy import select

import app.services.billing as billing_mod
from app.models import Device, Organization, SubscriptionStatus

_PW = "Password12345"


async def _register(client, session_factory, org="Bill Co", email="a@bill.com") -> dict[str, str]:
    from app.services.invites import InviteService
    async with session_factory() as session:
        _, code = await InviteService(session).create(note="t", expires_in_days=30)
    reg = await client.post("/api/v1/auth/register", json={
        "invite_code": code, "organization_name": org,
        "admin_name": "Admin", "admin_email": email, "admin_password": _PW,
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _org(session_factory, name) -> Organization:
    async with session_factory() as s:
        return (await s.execute(select(Organization).where(Organization.name == name))).scalar_one()


def _configure(monkeypatch, *, webhook=True):
    monkeypatch.setattr(billing_mod.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing_mod.settings, "stripe_price_id", "price_x")
    if webhook:
        monkeypatch.setattr(billing_mod.settings, "stripe_webhook_secret", "whsec_x")


async def _post_webhook(client, event, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda payload, sig, secret: event)
    return await client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t"}
    )


# -- inert until configured ---------------------------------------------------

async def test_status_inert_when_stripe_unconfigured(client, session_factory):
    headers = await _register(client, session_factory)
    r = await client.get("/api/v1/billing/status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["billing_enabled"] is False
    assert body["seat_type"] == "device"
    assert body["subscription_status"] == "trialing"
    assert body["writable"] is True
    assert body["has_subscription"] is False


async def test_checkout_400_when_unconfigured(client, session_factory):
    headers = await _register(client, session_factory)
    r = await client.post("/api/v1/billing/checkout", headers=headers)
    assert r.status_code == 400


# -- seats --------------------------------------------------------------------

async def test_seat_count_counts_active_devices(client, session_factory):
    headers = await _register(client, session_factory, org="Seat Co", email="s@seat.com")
    org = await _org(session_factory, "Seat Co")
    async with session_factory() as s:
        for i, active in enumerate([True, True, False]):
            s.add(Device(
                org_id=org.id, hostname=f"h{i}", machine_id=f"m{i}",
                os_version="win11", agent_version="1", token_hash=f"t{i}", is_active=active,
            ))
        await s.commit()
    body = (await client.get("/api/v1/billing/status", headers=headers)).json()
    assert body["seat_count"] == 2  # inactive/decommissioned devices are not billed


# -- checkout (configured) ----------------------------------------------------

async def test_checkout_returns_stripe_url_when_configured(client, session_factory, monkeypatch):
    _configure(monkeypatch, webhook=False)
    headers = await _register(client, session_factory, org="Checkout Co", email="c@co.com")
    monkeypatch.setattr(stripe.Customer, "create", lambda **kw: {"id": "cus_new"})
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kw: {"url": "https://checkout.stripe.test/x"})
    r = await client.post("/api/v1/billing/checkout", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://checkout.stripe.test/x"
    # customer id was persisted for later portal access
    assert (await _org(session_factory, "Checkout Co")).stripe_customer_id == "cus_new"


# -- webhooks drive subscription state ----------------------------------------

async def test_webhook_checkout_completed_activates_org(client, session_factory, monkeypatch):
    await _register(client, session_factory)
    org = await _org(session_factory, "Bill Co")
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: {
        "id": "sub_123", "status": "active", "current_period_end": 1893456000,
        "items": {"data": [{"id": "si_1", "quantity": 1, "current_period_end": 1893456000}]},
    })
    event = {"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": str(org.id), "customer": "cus_123", "subscription": "sub_123",
    }}}
    r = await _post_webhook(client, event, monkeypatch)
    assert r.status_code == 200, r.text

    refreshed = await _org(session_factory, "Bill Co")
    assert refreshed.subscription_status is SubscriptionStatus.ACTIVE
    assert refreshed.stripe_customer_id == "cus_123"
    assert refreshed.stripe_subscription_id == "sub_123"
    assert refreshed.current_period_end is not None


async def test_webhook_payment_failed_makes_org_read_only(client, session_factory, monkeypatch):
    headers = await _register(client, session_factory, org="PastDue Co", email="p@pd.com")
    org = await _org(session_factory, "PastDue Co")
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.stripe_customer_id, o.stripe_subscription_id = "cus_pd", "sub_pd"
        o.subscription_status = SubscriptionStatus.ACTIVE
        await s.commit()

    event = {"type": "invoice.payment_failed", "data": {"object": {
        "subscription": "sub_pd", "customer": "cus_pd", "lines": {"data": []},
    }}}
    r = await _post_webhook(client, event, monkeypatch)
    assert r.status_code == 200

    assert (await _org(session_factory, "PastDue Co")).subscription_status is SubscriptionStatus.PAST_DUE
    # The read-only gate now blocks writes...
    blocked = await client.post("/api/v1/users", headers=headers,
        json={"email": "n@pd.com", "full_name": "N", "password": _PW, "role": "user"})
    assert blocked.status_code == 402
    # ...but billing endpoints stay reachable so they can pay to recover.
    assert (await client.get("/api/v1/billing/status", headers=headers)).status_code == 200


async def test_webhook_subscription_deleted_cancels(client, session_factory, monkeypatch):
    await _register(client, session_factory, org="Gone Co", email="g@gone.com")
    org = await _org(session_factory, "Gone Co")
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.stripe_subscription_id, o.subscription_status = "sub_gone", SubscriptionStatus.ACTIVE
        await s.commit()

    event = {"type": "customer.subscription.deleted", "data": {"object": {
        "id": "sub_gone", "status": "canceled",
    }}}
    r = await _post_webhook(client, event, monkeypatch)
    assert r.status_code == 200
    assert (await _org(session_factory, "Gone Co")).subscription_status is SubscriptionStatus.CANCELED


async def test_webhook_bad_signature_is_rejected(client, session_factory, monkeypatch):
    _configure(monkeypatch)

    def _boom(payload, sig, secret):
        raise stripe.SignatureVerificationError("bad sig", sig)

    monkeypatch.setattr(stripe.Webhook, "construct_event", _boom)
    r = await client.post("/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert r.status_code == 400
