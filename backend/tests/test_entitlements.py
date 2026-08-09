"""Plan-based feature gating.

Two failure modes, both expensive and both silent:

  - Gating too little: every org gets every feature and the tiers are decoration. That is
    what was live before this — a $4.49 customer using $8.99 features.
  - Gating too much: a paying customer's product stops working. Worse than the leak, so the
    defaults here all fail OPEN, and those defaults are pinned by tests rather than trusted.
"""
import pytest

from app.models import Organization
from app.services.entitlements import (
    AI_ACT,
    AUDIT_VIEW,
    COMPLIANCE,
    ESSENTIAL,
    EXPERT,
    NOTIFICATIONS,
    PROFESSIONAL,
    features_for,
    normalise_plan,
)


async def _set_plan(session_factory, org_id, plan, overrides=None):
    async with session_factory() as session:
        org = await session.get(Organization, org_id)
        org.plan = plan
        org.entitlement_overrides = overrides
        await session.commit()


# ── The mapping itself ─────────────────────────────────────────────────────


def test_the_tiers_stack():
    assert features_for(ESSENTIAL) < features_for(PROFESSIONAL) < features_for(EXPERT)


def test_audit_and_notifications_stay_in_essential():
    """Deliberate, and against the pricing page's grouping.

    The audit trail is many customers' own compliance requirement — taking it away makes the
    entry tier a liability rather than a smaller product. Notifications likewise: an org that
    is never told a device went offline experiences a broken product, not a cheaper one.
    Expert's "full audit trail & export" is the CSV export and retention instead.
    """
    essential = features_for(ESSENTIAL)
    assert AUDIT_VIEW in essential
    assert NOTIFICATIONS in essential


def test_unattended_fixing_is_the_professional_line():
    assert AI_ACT not in features_for(ESSENTIAL)
    assert AI_ACT in features_for(PROFESSIONAL)


def test_a_legacy_plan_keeps_everything():
    """Orgs that predate tiers have had every feature since signup. Mapping them anywhere
    but Expert would take paid functionality away the moment this deployed."""
    for legacy in ("trial", "per-seat", "basic", "pro"):
        assert features_for(legacy) == features_for(EXPERT), legacy
        assert normalise_plan(legacy) == EXPERT


def test_an_unknown_plan_fails_open():
    """A typo in a plan name must not switch a customer's product off."""
    assert features_for("enterprise-gold") == features_for(EXPERT)


def test_overrides_add_and_remove():
    assert COMPLIANCE in features_for(ESSENTIAL, {COMPLIANCE: True})
    assert AI_ACT not in features_for(EXPERT, {AI_ACT: False})


# ── Enforcement, through the API ───────────────────────────────────────────


async def test_essential_cannot_reach_compliance(
    client, admin_headers, admin_user, session_factory
):
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL)
    resp = await client.get("/api/v1/compliance/summary", headers=admin_headers)
    # 402, not 403: the caller has the right role, their plan just doesn't include this.
    # "Ask your administrator" and "upgrade your plan" are different next steps.
    assert resp.status_code == 402, resp.text
    assert resp.headers.get("X-Astra-Required-Feature") == COMPLIANCE


async def test_expert_can(client, admin_headers, admin_user, session_factory):
    await _set_plan(session_factory, admin_user.org_id, EXPERT)
    assert (await client.get("/api/v1/compliance/summary", headers=admin_headers)).status_code == 200


async def test_an_override_opens_a_feature_for_one_org(
    client, admin_headers, admin_user, session_factory
):
    """The pilot / grandfathered case, which sales will need on day one."""
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL, {COMPLIANCE: True})
    assert (await client.get("/api/v1/compliance/summary", headers=admin_headers)).status_code == 200


async def test_essential_cannot_mass_remediate(
    client, admin_headers, admin_user, session_factory
):
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL)
    resp = await client.get("/api/v1/fleet/issues", headers=admin_headers)
    assert resp.status_code == 402


# ── The part that must NOT break ───────────────────────────────────────────


async def test_essential_still_gets_the_product(
    client, admin_headers, admin_user, session_factory
):
    """Gating is about what the tiers promise, not about crippling the cheap one. Devices,
    telemetry, the dashboard, notifications and the audit trail all keep working."""
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL)
    for path in (
        "/api/v1/devices",
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/overview",
        "/api/v1/notifications",
        "/api/v1/audit-logs",
    ):
        resp = await client.get(path, headers=admin_headers)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"


async def test_essential_can_still_run_every_fix_just_not_unattended(
    client, admin_headers, admin_user, session_factory
):
    """The Essential/Professional line is whether a human clears each action — NOT which
    actions exist. An Essential org that could no longer fix anything would be a broken
    product, and the pricing page doesn't claim that.
    """
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL)

    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "ent"}, headers=admin_headers
    )
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "ENT-PC",
        "machine_id": "ent-machine", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()

    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    # Created and runnable — it just waits for a person instead of going on its own.
    assert resp.json()["status"] == "pending_approval"


async def test_professional_runs_it_unattended(
    client, admin_headers, admin_user, session_factory
):
    await _set_plan(session_factory, admin_user.org_id, PROFESSIONAL)

    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "ent2"}, headers=admin_headers
    )
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "PRO-PC",
        "machine_id": "pro-machine", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()

    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns"},
        headers=admin_headers,
    )
    assert resp.json()["status"] == "approved"


async def test_lockdown_needs_professional(
    client, admin_headers, admin_user, session_factory
):
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL)

    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "ent3"}, headers=admin_headers
    )
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "LOCK-PC",
        "machine_id": "lock-machine", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()

    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "disable_local_account",
              "params": {"username": "jdoe"}, "reason": "offboarding"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "professional" in resp.text.lower()


async def test_the_dashboard_does_not_leak_expert_data(
    client, admin_headers, admin_user, session_factory
):
    """The overview endpoint aggregates compliance and fleet data by calling those services
    directly, so the routers' gates don't apply to it. Gating the compliance page while the
    same numbers arrive on the home screen would be a gate in name only — and this is the
    shape of leak that looks completely fine on screen.
    """
    await _set_plan(session_factory, admin_user.org_id, ESSENTIAL)
    body = (await client.get("/api/v1/dashboard/overview", headers=admin_headers)).json()

    assert body["compliance"] is None
    assert body["top_issues"] == []
    # The rest of the dashboard is Essential and must still be there.
    assert body["patch"] is not None
    assert "trend" in body


async def test_expert_still_sees_it_on_the_dashboard(
    client, admin_headers, admin_user, session_factory
):
    await _set_plan(session_factory, admin_user.org_id, EXPERT)
    body = (await client.get("/api/v1/dashboard/overview", headers=admin_headers)).json()
    assert body["compliance"] is not None


async def test_paying_does_not_upgrade_the_feature_tier(session_factory, admin_user):
    """A payment activates the subscription; it does not decide which tier was bought.

    apply_event used to set plan = "per-seat" on activation, and "per-seat" resolves to
    Expert — so an Essential customer's first successful charge silently handed them the
    whole product. Which tier an org is on is a commercial decision the operator makes.
    """
    from app.models import Organization, SubscriptionStatus
    from app.services.billing import BillingService
    from app.services.payments.base import SubscriptionEvent

    async with session_factory() as session:
        org = await session.get(Organization, admin_user.org_id)
        org.plan = ESSENTIAL
        org.provider_subscription_id = "sub_test_1"
        await session.commit()

    async with session_factory() as session:
        await BillingService(session).apply_event(SubscriptionEvent(
            org_id=admin_user.org_id,
            subscription_id="sub_test_1",
            status=SubscriptionStatus.ACTIVE,
            quantity=25,
        ))

    async with session_factory() as session:
        org = await session.get(Organization, admin_user.org_id)
        assert org.plan == ESSENTIAL, "paying silently upgraded the feature tier"
        # The parts billing IS responsible for still moved.
        assert org.subscription_status == SubscriptionStatus.ACTIVE
        assert org.license_count == 25


@pytest.mark.parametrize("stored", ["essential", " essential", "essential ", "  ESSENTIAL  ", "\tessential\n"])
def test_whitespace_around_a_plan_does_not_upgrade_the_customer(stored):
    """`features_for` fell back to Expert for anything it did not recognise — deliberate, so
    a typo cannot switch a paying customer's product off. But " essential " is not an
    unknown plan, it is Essential with a space, which is what a CSV import or a hand-edited
    row produces. It was silently handing that customer all 16 features."""
    assert features_for(stored) == features_for("essential")


def test_the_label_and_the_grant_read_the_plan_the_same_way():
    """normalise_plan drives what the admin is told; features_for drives what they get.
    Two different readings of the same string is how a page says Essential while the API
    allows Expert."""
    for stored in [" essential ", "PROFESSIONAL", "expert "]:
        label = normalise_plan(stored)
        assert features_for(stored) == features_for(label), stored
