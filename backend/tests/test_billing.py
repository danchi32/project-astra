"""Phase B: licensed per-seat Stripe billing + hard enrollment cap + operator discount.

Stripe network calls are monkeypatched — these tests verify our own logic. No real
Stripe calls, no keys needed.
"""
import stripe
from sqlalchemy import select

import app.services.billing as billing_mod
from app.models import Device, Organization, SubscriptionStatus, User

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


async def _promote(session_factory, email):
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()


async def _add_devices(session_factory, org_id, n, active=True):
    async with session_factory() as s:
        base = (await s.execute(select(Device).where(Device.org_id == org_id))).scalars().all()
        start = len(base)
        for i in range(start, start + n):
            s.add(Device(
                org_id=org_id, hostname=f"h{i}", machine_id=f"m{i}",
                os_version="win11", agent_version="1", token_hash=f"t{i}", is_active=active,
            ))
        await s.commit()


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
    assert body["licenses"] == 0
    assert body["seats_used"] == 0
    assert body["writable"] is True
    assert body["has_subscription"] is False


async def test_checkout_400_when_unconfigured(client, session_factory):
    headers = await _register(client, session_factory)
    r = await client.post("/api/v1/billing/checkout", headers=headers, json={"quantity": 3})
    assert r.status_code == 400


# -- seats / licenses ---------------------------------------------------------

async def test_seats_used_counts_active_devices(client, session_factory):
    headers = await _register(client, session_factory, org="Seat Co", email="s@seat.com")
    org = await _org(session_factory, "Seat Co")
    await _add_devices(session_factory, org.id, 2, active=True)
    await _add_devices(session_factory, org.id, 1, active=False)
    body = (await client.get("/api/v1/billing/status", headers=headers)).json()
    assert body["seats_used"] == 2  # decommissioned devices don't consume a license


async def test_checkout_returns_stripe_url_when_configured(client, session_factory, monkeypatch):
    _configure(monkeypatch, webhook=False)
    headers = await _register(client, session_factory, org="Checkout Co", email="c@co.com")
    captured = {}
    monkeypatch.setattr(stripe.Customer, "create", lambda **kw: {"id": "cus_new"})

    def _create(**kw):
        captured.update(kw)
        return {"url": "https://checkout.stripe.test/x"}

    monkeypatch.setattr(stripe.checkout.Session, "create", _create)
    r = await client.post("/api/v1/billing/checkout", headers=headers, json={"quantity": 5})
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://checkout.stripe.test/x"
    assert captured["line_items"][0]["quantity"] == 5  # buys the requested licenses


# -- hard enrollment cap ------------------------------------------------------

async def test_license_cap_blocks_enrollment(client, session_factory):
    headers = await _register(client, session_factory, org="Cap Co", email="cap@co.com")
    org = await _org(session_factory, "Cap Co")
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.license_count = 1  # one purchased license
        await s.commit()

    tok = (await client.post("/api/v1/devices/enrollment-tokens", headers=headers, json={"name": "f"})).json()["token"]

    def enroll(mid):
        return client.post("/api/v1/agent/enroll", json={
            "enrollment_token": tok, "hostname": mid, "machine_id": mid,
            "os_version": "Windows 11", "agent_version": "0.1.0"})

    first = await enroll("pc-1")
    assert first.status_code in (200, 201), first.text
    second = await enroll("pc-2")
    assert second.status_code == 400
    assert "license" in second.text.lower()


async def test_uncapped_when_no_licenses(client, session_factory):
    # A trial org (license_count == 0) can enroll freely.
    headers = await _register(client, session_factory, org="Free Co", email="free@co.com")
    tok = (await client.post("/api/v1/devices/enrollment-tokens", headers=headers, json={"name": "f"})).json()["token"]
    for mid in ("a", "b", "c"):
        r = await client.post("/api/v1/agent/enroll", json={
            "enrollment_token": tok, "hostname": mid, "machine_id": mid,
            "os_version": "Windows 11", "agent_version": "0.1.0"})
        assert r.status_code in (200, 201), r.text


async def test_cannot_reduce_licenses_below_used(client, session_factory):
    headers = await _register(client, session_factory, org="Reduce Co", email="r@co.com")
    org = await _org(session_factory, "Reduce Co")
    await _add_devices(session_factory, org.id, 2, active=True)
    r = await client.post("/api/v1/billing/licenses", headers=headers, json={"count": 1})
    assert r.status_code == 400
    assert "in use" in r.text.lower()


# -- webhooks drive subscription state + license count ------------------------

async def test_webhook_checkout_completed_activates_and_sets_licenses(client, session_factory, monkeypatch):
    await _register(client, session_factory)
    org = await _org(session_factory, "Bill Co")
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: {
        "id": "sub_123", "status": "active", "current_period_end": 1893456000,
        "items": {"data": [{"id": "si_1", "quantity": 7, "current_period_end": 1893456000}]},
    })
    event = {"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": str(org.id), "customer": "cus_123", "subscription": "sub_123",
    }}}
    r = await _post_webhook(client, event, monkeypatch)
    assert r.status_code == 200, r.text

    refreshed = await _org(session_factory, "Bill Co")
    assert refreshed.subscription_status is SubscriptionStatus.ACTIVE
    assert refreshed.stripe_subscription_id == "sub_123"
    assert refreshed.license_count == 7  # licenses = Stripe subscription quantity


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

    blocked = await client.post("/api/v1/users", headers=headers,
        json={"email": "n@pd.com", "full_name": "N", "password": _PW, "role": "user"})
    assert blocked.status_code == 402
    assert (await client.get("/api/v1/billing/status", headers=headers)).status_code == 200


async def test_webhook_bad_signature_is_rejected(client, session_factory, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(stripe.Webhook, "construct_event",
                        lambda p, s, sec: (_ for _ in ()).throw(stripe.SignatureVerificationError("bad", s)))
    r = await client.post("/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert r.status_code == 400


# -- operator discount (super-admin) ------------------------------------------

async def test_super_admin_sets_and_clears_discount(client, session_factory):
    headers = await _register(client, session_factory, org="Disc Co", email="disc@co.com")
    await _promote(session_factory, "disc@co.com")
    oid = str((await _org(session_factory, "Disc Co")).id)

    applied = await client.post(f"/api/v1/platform/organizations/{oid}/discount",
                                headers=headers, json={"percent": 20})
    assert applied.status_code == 200, applied.text
    assert applied.json()["discount_percent"] == 20
    assert (await _org(session_factory, "Disc Co")).discount_percent == 20

    cleared = await client.delete(f"/api/v1/platform/organizations/{oid}/discount", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["discount_percent"] is None


async def test_discount_requires_platform_admin(client, session_factory):
    headers = await _register(client, session_factory, org="NoPerm Co", email="np@co.com")
    oid = str((await _org(session_factory, "NoPerm Co")).id)
    r = await client.post(f"/api/v1/platform/organizations/{oid}/discount",
                          headers=headers, json={"percent": 10})
    assert r.status_code == 403
