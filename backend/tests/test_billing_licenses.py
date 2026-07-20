"""set_licenses must route through the org's actual payment rail (Razorpay/Paddle/PayPal),
not the legacy Stripe path — regression for a PayPal subscriber getting a false
'No active subscription' error."""
from app.models import Organization, SubscriptionStatus
from app.services.billing import BillingService
from app.services.exceptions import ValidationError
from app.services.payments import paypal_provider as paypal_mod


async def _org(session, **kw) -> Organization:
    org = Organization(name="PayCo", subscription_status=SubscriptionStatus.ACTIVE, **kw)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def test_set_licenses_routes_to_paypal(session_factory, monkeypatch):
    calls: dict = {}

    async def fake_set_quantity(self, *, org, quantity):
        calls["quantity"] = quantity

    monkeypatch.setattr(paypal_mod.PayPalProvider, "set_quantity", fake_set_quantity)

    async with session_factory() as session:
        org = await _org(
            session, billing_provider="paypal",
            provider_subscription_id="I-SUB1", license_count=2,
        )
        count, _used, msg = await BillingService(session).set_licenses(org, 5)

    assert count == 5
    assert calls["quantity"] == 5          # PayPal's rail was actually asked to revise
    assert org.license_count == 5
    assert "5 license" in msg


async def test_set_licenses_resets_stale_paypal_subscription(session_factory, monkeypatch):
    """A 404 from PayPal (subscription created in a different env, or cancelled) clears the
    dead link so the org can re-subscribe, instead of showing a raw PayPal error."""
    from app.services.exceptions import SubscriptionNotFound, ValidationError

    async def fake_set_quantity(self, *, org, quantity):
        raise SubscriptionNotFound("PayPal could not find that subscription.")

    monkeypatch.setattr(paypal_mod.PayPalProvider, "set_quantity", fake_set_quantity)

    async with session_factory() as session:
        org = await _org(
            session, billing_provider="paypal",
            provider_subscription_id="I-STALE", license_count=2,
        )
        try:
            await BillingService(session).set_licenses(org, 4)
            assert False, "expected a validation error"
        except ValidationError as exc:
            assert "subscribe again" in str(exc).lower()
        # The dead link was cleared, so the Subscribe flow can return.
        assert org.provider_subscription_id is None
        assert org.billing_provider is None


async def test_set_licenses_without_subscription_still_guards(session_factory):
    async with session_factory() as session:
        org = await _org(session, license_count=0)  # no provider, no subscription id
        try:
            await BillingService(session).set_licenses(org, 3)
            assert False, "expected a validation error"
        except ValidationError as exc:
            assert "subscribe first" in str(exc).lower()
