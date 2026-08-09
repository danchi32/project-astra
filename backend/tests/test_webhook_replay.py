"""A signature proves a webhook is authentic. It does not prove it is new.

Every rail here signs the request body, so a captured `subscription.activated` payload
stayed valid indefinitely — replay it after a cancellation and the org went back to ACTIVE,
which is the flag `org_is_writable` reads. Delivery order is not guaranteed either, so a
late `activated` arriving after `canceled` did the same thing with nobody attacking
anything.

These tests are about `apply_event`, the one place every rail converges.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Organization, SubscriptionStatus, WebhookEvent
from app.services.billing import BillingService
from app.services.payments import SubscriptionEvent

T0 = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _event(org_id, status, *, event_id, at, quantity=10, provider="paddle"):
    return SubscriptionEvent(
        org_id=org_id, status=status, quantity=quantity,
        subscription_id="sub_1", customer_id="cus_1",
        provider=provider, event_id=event_id, occurred_at=at,
    )


async def _org(session):
    org = Organization(name="Replay Co")
    session.add(org)
    await session.flush()
    return org


async def test_the_same_delivery_twice_is_applied_once(session_factory):
    """The rails retry, and a captured payload can be resent by anyone who has it."""
    async with session_factory() as s:
        org = await _org(s)
        svc = BillingService(s)
        first = await svc.apply_event(_event(org.id, SubscriptionStatus.ACTIVE,
                                             event_id="evt_1", at=T0))
        second = await svc.apply_event(_event(org.id, SubscriptionStatus.ACTIVE,
                                              event_id="evt_1", at=T0))
        assert first["applied"] is True
        assert second["applied"] is False
        assert second["reason"] == "duplicate"

        rows = (await s.execute(select(WebhookEvent))).scalars().all()
        assert len(rows) == 1, "one delivery, one record"


async def test_replaying_an_activation_cannot_revive_a_cancelled_org(session_factory):
    """The attack the dedupe exists for: capture the activation, cancel, replay."""
    async with session_factory() as s:
        org = await _org(s)
        svc = BillingService(s)
        activation = _event(org.id, SubscriptionStatus.ACTIVE, event_id="evt_act", at=T0)
        await svc.apply_event(activation)
        await svc.apply_event(_event(org.id, SubscriptionStatus.CANCELED,
                                     event_id="evt_cancel", at=T0 + timedelta(hours=1),
                                     quantity=0))
        assert org.subscription_status is SubscriptionStatus.CANCELED

        replayed = await svc.apply_event(activation)
        assert replayed["applied"] is False
        await s.refresh(org)
        assert org.subscription_status is SubscriptionStatus.CANCELED, (
            "a replayed activation must not restore a cancelled subscription"
        )
        assert org.license_count == 0


async def test_a_late_activation_does_not_overtake_a_newer_cancellation(session_factory):
    """No rail guarantees ordering. This one needs no attacker at all — it is Tuesday."""
    async with session_factory() as s:
        org = await _org(s)
        svc = BillingService(s)
        await svc.apply_event(_event(org.id, SubscriptionStatus.CANCELED,
                                     event_id="evt_cancel", at=T0 + timedelta(hours=1),
                                     quantity=0))
        out = await svc.apply_event(_event(org.id, SubscriptionStatus.ACTIVE,
                                           event_id="evt_act", at=T0))
        assert out["applied"] is False
        assert out["reason"] == "out of order"
        await s.refresh(org)
        assert org.subscription_status is SubscriptionStatus.CANCELED


async def test_a_newer_event_still_applies(session_factory):
    """The ordering guard must not freeze the org at its first event."""
    async with session_factory() as s:
        org = await _org(s)
        svc = BillingService(s)
        await svc.apply_event(_event(org.id, SubscriptionStatus.ACTIVE,
                                     event_id="evt_1", at=T0))
        out = await svc.apply_event(_event(org.id, SubscriptionStatus.PAST_DUE,
                                           event_id="evt_2", at=T0 + timedelta(days=1)))
        assert out["applied"] is True
        await s.refresh(org)
        assert org.subscription_status is SubscriptionStatus.PAST_DUE


async def test_an_event_with_no_id_is_still_applied(session_factory):
    """Dropping a real subscription change because we could not identify the delivery is
    worse than applying it twice. It falls through to the ordering check instead."""
    async with session_factory() as s:
        org = await _org(s)
        svc = BillingService(s)
        out = await svc.apply_event(SubscriptionEvent(
            org_id=org.id, status=SubscriptionStatus.ACTIVE, quantity=5,
            provider="stripe", event_id=None, occurred_at=None,
        ))
        assert out["applied"] is True
        await s.refresh(org)
        assert org.subscription_status is SubscriptionStatus.ACTIVE
