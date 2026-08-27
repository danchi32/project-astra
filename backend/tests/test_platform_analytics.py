"""The operator console's analytical layer: invoice-backed revenue and per-customer health.

The scoring assertions here matter more than the plumbing ones. A health score that
silently drifts is worse than no score, because the operator acts on it.
"""
from datetime import date, timedelta

from sqlalchemy import select

from app.models import (
    Device,
    Invoice,
    InvoiceStatus,
    Organization,
    RemediationStatus,
    RemediationTask,
    SubscriptionStatus,
    User,
)
from app.models.base import utcnow
from app.services.invites import InviteService

_PW = "Password12345"


async def _issue_invite(session_factory) -> str:
    async with session_factory() as session:
        _, raw = await InviteService(session).create(note="t", expires_in_days=30)
    return raw


async def _register_org(client, session_factory, org, email):
    return await client.post("/api/v1/auth/register", json={"terms_accepted": True,
        "invite_code": await _issue_invite(session_factory), "organization_name": org,
        "admin_name": "Admin", "admin_email": email, "admin_password": _PW,
    })


async def _operator(client, session_factory, org="Ops Co", email="op@ops.com"):
    reg = await _register_org(client, session_factory, org, email)
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _org_by_name(session_factory, name) -> Organization:
    async with session_factory() as s:
        return (await s.execute(
            select(Organization).where(Organization.name == name)
        )).scalar_one()


async def test_analytics_requires_platform_admin(client, session_factory):
    """A normal org admin must not see other customers' revenue or health."""
    reg = await _register_org(client, session_factory, "Plain Co", "plain@co.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    response = await client.get("/api/v1/platform/analytics", headers=headers)
    assert response.status_code == 403, response.text


async def test_analytics_excludes_operator_own_org(client, session_factory):
    headers = await _operator(client, session_factory)
    await _register_org(client, session_factory, "Cust Co", "a@cust.com")

    response = await client.get("/api/v1/platform/analytics", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    names = {r["org_name"] for r in body["org_health"]}
    assert "Cust Co" in names
    assert "Ops Co" not in names  # the operator's own workspace is not a customer
    assert len(body["revenue_by_month"]) == 12
    # No invoices anywhere yet, so there is no currency to denominate a trend in.
    assert body["revenue_currency"] is None
    assert body["other_currencies"] == []


async def test_health_penalises_a_dark_fleet(client, session_factory):
    """The core signal: seats sold, nothing reporting in, nobody using it."""
    headers = await _operator(client, session_factory, org="Dark Ops", email="op@darkops.com")
    await _register_org(client, session_factory, "Dark Co", "a@darkco.com")
    org = await _org_by_name(session_factory, "Dark Co")

    async with session_factory() as s:
        fresh = await s.get(Organization, org.id)
        fresh.license_count = 50
        fresh.subscription_status = SubscriptionStatus.ACTIVE
        await s.commit()

    body = (await client.get("/api/v1/platform/analytics", headers=headers)).json()
    row = next(r for r in body["org_health"] if r["org_name"] == "Dark Co")

    assert row["devices"] == 0
    assert row["health_band"] == "at_risk"
    assert "No devices enrolled" in row["risk_reasons"]
    # Connectivity is forfeited entirely; adoption cannot be judged against zero devices
    # deployed on 50 licences either.
    assert row["health_score"] < 50


async def test_health_rewards_a_live_fleet(client, session_factory):
    headers = await _operator(client, session_factory, org="Live Ops", email="op@liveops.com")
    await _register_org(client, session_factory, "Live Co", "a@liveco.com")
    org = await _org_by_name(session_factory, "Live Co")

    async with session_factory() as s:
        fresh = await s.get(Organization, org.id)
        fresh.license_count = 4
        fresh.subscription_status = SubscriptionStatus.ACTIVE
        for i in range(4):
            s.add(Device(
                org_id=org.id, hostname=f"pc-{i}", machine_id=f"live-{i}", os_version="Win 11",
                agent_version="0.8.2", token_hash=f"live-token-{i}", last_seen_at=utcnow(),
            ))
        await s.commit()

    body = (await client.get("/api/v1/platform/analytics", headers=headers)).json()
    row = next(r for r in body["org_health"] if r["org_name"] == "Live Co")

    assert row["devices"] == 4 and row["online_devices"] == 4
    assert row["online_pct"] == 100.0
    assert row["seat_utilisation"] == 1.0
    assert row["health_band"] == "healthy"
    assert row["risk_reasons"] == []


async def test_billing_trouble_overrides_a_good_score(client, session_factory):
    """A healthy fleet that stopped paying is still an at-risk account."""
    headers = await _operator(client, session_factory, org="Due Ops", email="op@dueops.com")
    await _register_org(client, session_factory, "Due Co", "a@dueco.com")
    org = await _org_by_name(session_factory, "Due Co")

    async with session_factory() as s:
        fresh = await s.get(Organization, org.id)
        fresh.license_count = 2
        fresh.subscription_status = SubscriptionStatus.PAST_DUE
        for i in range(2):
            s.add(Device(
                org_id=org.id, hostname=f"due-{i}", machine_id=f"due-{i}", os_version="Win 11",
                agent_version="0.8.2", token_hash=f"due-token-{i}", last_seen_at=utcnow(),
            ))
        await s.commit()

    body = (await client.get("/api/v1/platform/analytics", headers=headers)).json()
    row = next(r for r in body["org_health"] if r["org_name"] == "Due Co")

    assert row["health_score"] >= 75          # the fleet itself is fine
    assert row["health_band"] == "at_risk"    # ...and it still needs attention
    assert row["risk_reasons"][0] == "Payment past due"


async def test_failing_remediations_are_called_out(client, session_factory):
    headers = await _operator(client, session_factory, org="Fail Ops", email="op@failops.com")
    await _register_org(client, session_factory, "Fail Co", "a@failco.com")
    org = await _org_by_name(session_factory, "Fail Co")

    async with session_factory() as s:
        device = Device(org_id=org.id, hostname="fail-1", machine_id="fail-1", os_version="Win 11",
                        agent_version="0.8.2", token_hash="fail-token", last_seen_at=utcnow())
        s.add(device)
        await s.flush()
        for i in range(4):
            s.add(RemediationTask(
                org_id=org.id, device_id=device.id, action_id="flush_dns", tier="automatic",
                reason="DNS resolution failing", source="test",
                status=RemediationStatus.FAILED if i < 3 else RemediationStatus.SUCCEEDED,
            ))
        await s.commit()

    body = (await client.get("/api/v1/platform/analytics", headers=headers)).json()
    row = next(r for r in body["org_health"] if r["org_name"] == "Fail Co")

    assert row["remediation_total_30d"] == 4
    assert row["remediation_failed_30d"] == 3
    assert any("75% of fixes failed" in r for r in row["risk_reasons"])


async def test_revenue_trend_reads_invoices_and_picks_one_currency(client, session_factory):
    """Invoiced and collected are separate series, and paise are never added to cents."""
    headers = await _operator(client, session_factory, org="Rev Ops", email="op@revops.com")
    await _register_org(client, session_factory, "Rev Co", "a@revco.com")
    org = await _org_by_name(session_factory, "Rev Co")

    today = date.today()
    now = utcnow()
    async with session_factory() as s:
        # Two USD invoices — one paid, one still open.
        s.add(Invoice(
            org_id=org.id, number="ASTRA-1", issued_on=today, currency="USD",
            total_cents=50_000, status=InvoiceStatus.PAID, paid_at=now,
        ))
        s.add(Invoice(
            org_id=org.id, number="ASTRA-2", issued_on=today, currency="USD",
            total_cents=20_000, status=InvoiceStatus.OPEN,
        ))
        # A lone INR invoice must not be folded into the USD trend.
        s.add(Invoice(
            org_id=org.id, number="ASTRA-3", issued_on=today, currency="INR",
            total_cents=999_999, status=InvoiceStatus.PAID, paid_at=now,
        ))
        await s.commit()

    body = (await client.get("/api/v1/platform/analytics", headers=headers)).json()

    assert body["revenue_currency"] == "USD"
    assert body["other_currencies"] == ["INR"]

    this_month = f"{today.year:04d}-{today.month:02d}"
    month = next(m for m in body["revenue_by_month"] if m["month"] == this_month)
    assert month["invoiced_cents"] == 70_000     # both USD invoices were billed
    assert month["collected_cents"] == 50_000    # only one was paid
    assert month["invoice_count"] == 2           # the INR row is excluded entirely
    assert body["outstanding_cents"] == 20_000
    assert body["collected_90d_cents"] == 50_000


async def test_trial_conversion_counts_only_finished_trials(client, session_factory):
    headers = await _operator(client, session_factory, org="Conv Ops", email="op@conv.com")
    await _register_org(client, session_factory, "Converted Co", "a@conv1.com")
    await _register_org(client, session_factory, "Lapsed Co", "a@conv2.com")
    await _register_org(client, session_factory, "Still Trialing Co", "a@conv3.com")

    past = utcnow() - timedelta(days=1)
    async with session_factory() as s:
        converted = (await s.execute(
            select(Organization).where(Organization.name == "Converted Co")
        )).scalar_one()
        converted.trial_ends_at = past
        converted.subscription_status = SubscriptionStatus.ACTIVE

        lapsed = (await s.execute(
            select(Organization).where(Organization.name == "Lapsed Co")
        )).scalar_one()
        lapsed.trial_ends_at = past
        lapsed.subscription_status = SubscriptionStatus.CANCELED
        await s.commit()

    body = (await client.get("/api/v1/platform/analytics", headers=headers)).json()

    # Two trials have run out; one of them is paying. The org still inside its trial is
    # not counted either way — it has not had the chance to convert yet.
    assert body["trial_conversion_rate"] == 50.0
    assert body["canceled_orgs"] == 1
    assert body["churn_rate"] == 50.0
