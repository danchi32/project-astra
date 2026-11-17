"""J1 · Brief: on demand, every line a count SAVIO recorded."""
from datetime import timedelta

from sqlalchemy import select

from app.models import Asset, AssetCategory, AuditLog, RemediationSource, RemediationStatus, RemediationTask
from app.models.base import utcnow
from app.services.email import EmailService


async def _enroll(client, admin_headers, host):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": host, "machine_id": host.lower(),
        "os_version": "Windows 11", "agent_version": "0.15.0"})).json()
    return r["device_id"]


async def _seed(client, admin_headers, session_factory, admin_user):
    device_id = await _enroll(client, admin_headers, "BRIEF-1")
    await _enroll(client, admin_headers, "BRIEF-2")
    now = utcnow()

    def task(status, done_ago, **kw):
        return RemediationTask(org_id=admin_user.org_id, device_id=device_id, action_id="clear_temp",
                               tier="automatic", reason="t", source=RemediationSource.ASSISTANT,
                               status=status, completed_at=now - done_ago if done_ago else None, **kw)

    async with session_factory() as s:
        s.add_all([
            task(RemediationStatus.SUCCEEDED, timedelta(hours=2), evidence={"verdict": "improved"}),
            task(RemediationStatus.SUCCEEDED, timedelta(days=3)),          # this week, not today
            task(RemediationStatus.FAILED, timedelta(hours=1)),
            task(RemediationStatus.PENDING_APPROVAL, None),
            Asset(org_id=admin_user.org_id, name="<script>alert(1)</script> Laptop",
                  category=AssetCategory.LAPTOP,
                  warranty_expiry=(now + timedelta(days=10)).date().isoformat()),
        ])
        s.add(AuditLog(org_id=admin_user.org_id, actor_id=None, action="ai.proposal_refused",
                       target_type="device", target_id=str(device_id),
                       detail={"action": "reset_local_password", "why": "admin_only", "device": "BRIEF-1"}))
        await s.commit()
    await client.patch("/api/v1/settings/organization", headers=admin_headers,
                       json={"it_hourly_cost": 1200, "minutes_per_fix": 30})


def _lines(brief, key):
    return next((s["lines"] for s in brief["sections"] if s["key"] == key), [])


async def test_daily_brief_in_english(client, admin_headers, session_factory, admin_user):
    await _seed(client, admin_headers, session_factory, admin_user)
    r = await client.get("/api/v1/reports/brief?period=day", headers=admin_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["title"] == "Your IT today"
    assert _lines(b, "fleet")[0] == "2 computers, 0 online now."   # enrolled, not yet reporting
    healing = _lines(b, "healing")
    assert healing[0] == "1 problem(s) fixed with nobody needing to step in."
    assert "Worth about ₹600, at your hourly IT cost." in healing          # 1 x 30 min x ₹1200
    assert "1 of those fixes were measured and shown to work." in healing
    attention = _lines(b, "attention")
    for expected in ("1 fix(es) did not work and may need a person.",
                     "1 fix(es) are waiting for someone to approve them.",
                     "1 AI request(s) were refused because the assistant may not do that.",
                     "1 warranty(ies) end in the next 30 days."):
        assert expected in attention, attention
    assert b["headline"] == "1 fixed automatically; 4 thing(s) need your attention."
    assert not any("have not checked in" in line for line in attention)   # just enrolled, not silent

    # A PC that really has been quiet for over a day is called out.
    from app.models import Device
    async with session_factory() as s:
        quiet = (await s.execute(select(Device).where(Device.hostname == "BRIEF-2"))).scalars().one()
        quiet.last_seen_at = utcnow() - timedelta(days=2)
        await s.commit()
    b = (await client.get("/api/v1/reports/brief?period=day", headers=admin_headers)).json()
    assert "1 computer(s) have not checked in for over a day." in _lines(b, "attention")


async def test_weekly_brief_counts_the_week(client, admin_headers, session_factory, admin_user):
    await _seed(client, admin_headers, session_factory, admin_user)
    b = (await client.get("/api/v1/reports/brief?period=week", headers=admin_headers)).json()
    assert b["title"] == "Your IT this week"
    assert _lines(b, "healing")[0] == "2 problem(s) fixed with nobody needing to step in."


async def test_unknown_period_is_refused(client, admin_headers):
    assert (await client.get("/api/v1/reports/brief?period=month", headers=admin_headers)).status_code == 422


async def test_email_goes_to_the_asker_only_escaped_and_audited(
        client, admin_headers, user_headers, session_factory, admin_user, monkeypatch):
    await _seed(client, admin_headers, session_factory, admin_user)
    sent = []

    async def fake_send(self, *, to, subject, html, **kw):
        sent.append((to, subject, html))
        return True

    monkeypatch.setattr(EmailService, "send", fake_send)
    r = await client.post("/api/v1/reports/brief/email", headers=admin_headers,
                          json={"period": "week"})
    assert r.status_code == 200 and r.json() == {"sent": True, "to": admin_user.email}
    [(to, subject, html)] = sent
    assert to == admin_user.email and subject == "SAVIO · Your IT this week"
    assert "<script>" not in html                 # asset names are escaped in the e-mail

    for _ in range(4):
        assert (await client.post("/api/v1/reports/brief/email", headers=admin_headers, json={})).status_code == 200
    assert (await client.post("/api/v1/reports/brief/email", headers=admin_headers, json={})).status_code == 409

    async with session_factory() as s:
        rows = (await s.execute(select(AuditLog).where(AuditLog.action == "report.brief_emailed"))).scalars().all()
    assert len(rows) == 5 and rows[0].detail["sent"] is True
    assert (await client.get("/api/v1/reports/brief", headers=user_headers)).status_code == 403
    assert (await client.post("/api/v1/reports/brief/email", headers=user_headers, json={})).status_code == 403
