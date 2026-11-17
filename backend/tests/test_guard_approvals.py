"""Phase 3 · D7 approvals: asked for from the PC, decided by an admin (audited), and served
back to that PC only while in force. Narrow: one person, PC, site and channel."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AuditLog, GuardApproval, Notification
from tests.test_browser_policy import _enroll, _guard_on
from tests.test_guard_events import _event


def _ask(**over):
    return _event(mode="approve", action="approve", outcome="requested", **over)


async def _post(client, h, *events):
    r = await client.post("/api/v1/agent/guard/events", headers=h, json={"events": list(events)})
    assert r.status_code == 204, r.text


async def test_request_approve_and_serve(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers, "SALES-PC")
    await _post(client, h, _ask(), _ask())                       # asked twice: one request
    assert (await client.get("/api/v1/agent/guard/approvals", headers=h)).json() == []

    rows = (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()
    assert len(rows) == 1 and rows[0]["status"] == "pending" and rows[0]["hostname"] == "SALES-PC"
    async with session_factory() as s:
        note = (await s.execute(select(Notification).where(Notification.title == "Approval requested"))).scalars().one()
    # Every role reads notifications; who asked for what is for admins only (review H1).
    assert "asha" not in note.message and "chatgpt" not in note.message and "SALES-PC" not in note.message

    seen = rows[0]["requested_at"]
    r = await client.post(f"/api/v1/guard/approvals/{rows[0]['id']}/approve", headers=admin_headers,
                          json={"minutes": 15, "requested_at": seen})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    served = (await client.get("/api/v1/agent/guard/approvals", headers=h)).json()
    assert [(x["windows_user"], x["site"], x["channel"]) for x in served] == [(r"PC-1\asha", "chatgpt.com", "paste")]
    until = datetime.fromisoformat(served[0]["valid_until"])
    assert timedelta(minutes=14) < until - datetime.now(UTC) <= timedelta(minutes=15)

    # Decided once; a second decision is refused. Both outcomes audited.
    again = await client.post(f"/api/v1/guard/approvals/{rows[0]['id']}/deny", headers=admin_headers,
                              json={"requested_at": seen})
    assert again.status_code == 409
    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.approval_approve"))).scalars().one()
    assert audit.detail["minutes"] == 15 and audit.detail["site"] == "chatgpt.com"

    # Another PC of the same org gets nothing.
    _, other = await _enroll(client, admin_headers, "OTHER-PC")
    assert (await client.get("/api/v1/agent/guard/approvals", headers=other)).json() == []


async def test_deny_expire_and_end(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    device_id, h = await _enroll(client, admin_headers)
    await _post(client, h, _ask(site="claude.ai"))
    a = (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()[0]
    r = await client.post(f"/api/v1/guard/approvals/{a['id']}/deny", headers=admin_headers, json={"requested_at": a["requested_at"]})
    assert r.json()["status"] == "denied"
    assert (await client.get("/api/v1/agent/guard/approvals", headers=h)).json() == []

    async with session_factory() as s:
        old = GuardApproval(org_id=admin_user.org_id, device_id=device_id, windows_user="x", site="a.in", channel="paste",
                            counts={}, contact_list=False, keyword_hits=0, status="pending",
                            requested_at=datetime.now(UTC) - timedelta(days=2))
        over = GuardApproval(org_id=admin_user.org_id, device_id=device_id, windows_user="x", site="b.in", channel="file",
                             counts={}, contact_list=False, keyword_hits=0, status="approved",
                             requested_at=datetime.now(UTC) - timedelta(hours=2),
                             valid_until=datetime.now(UTC) - timedelta(minutes=1))
        s.add_all([old, over])
        await s.commit()
        old_id = old.id
    listed = (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()
    statuses = {r["site"]: r["status"] for r in listed}
    assert statuses == {"claude.ai": "denied", "a.in": "expired", "b.in": "ended"}
    old_seen = next(r["requested_at"] for r in listed if r["site"] == "a.in")
    r = await client.post(f"/api/v1/guard/approvals/{old_id}/approve", headers=admin_headers, json={"requested_at": old_seen})
    assert r.status_code == 409
    assert (await client.get("/api/v1/agent/guard/approvals", headers=h)).json() == []


async def test_bounds_and_roles(client, admin_headers, session_factory, admin_user, org):
    from app.models import UserRole
    from tests.conftest import _create_user, auth_headers

    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    await _post(client, h, _ask())
    a = (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()[0]
    for minutes in (0, 4, 481):
        r = await client.post(f"/api/v1/guard/approvals/{a['id']}/approve", headers=admin_headers,
                              json={"minutes": minutes, "requested_at": a["requested_at"]})
        assert r.status_code == 422, minutes
    await _create_user(session_factory, org.id, "tech@acme.com", "TechPassw0rd!2345", UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", "TechPassw0rd!2345")
    assert (await client.get("/api/v1/guard/approvals", headers=tech)).status_code == 403
    r = await client.post(f"/api/v1/guard/approvals/{a['id']}/approve", headers=tech, json={"requested_at": a["requested_at"]})
    assert r.status_code == 403
    # An approve event carries no reason; a warn event cannot be "requested".
    for bad in (_ask(reason="approved"), _event(outcome="requested")):
        r = await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [bad]})
        assert r.status_code == 422, bad


async def test_an_approval_covers_what_the_admin_saw(client, admin_headers, session_factory, admin_user):
    """Review M3: if the device changes what was found after the admin looked, the decision is
    refused; an unchanged repeat does not move the request."""
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    await _post(client, h, _ask(counts={"Email": 1}))
    a = (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()[0]
    await _post(client, h, _ask(counts={"Email": 1}))                      # the same again: unchanged
    assert (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()[0]["requested_at"] == a["requested_at"]

    await _post(client, h, _ask(counts={"Aadhaar": 5000}, contact_list=True))   # bait and switch
    r = await client.post(f"/api/v1/guard/approvals/{a['id']}/approve", headers=admin_headers,
                          json={"minutes": 480, "requested_at": a["requested_at"]})
    assert r.status_code == 409 and "changed" in r.json()["detail"]
    fresh = (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()[0]
    assert fresh["counts"] == {"Aadhaar": 5000} and fresh["status"] == "pending"


async def test_a_device_cannot_flood_requests_or_notifications(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    await _post(client, h, *[_ask(site=f"s{i}.example.com") for i in range(30)])
    async with session_factory() as s:
        pending = (await s.execute(select(GuardApproval))).scalars().all()
        notes = (await s.execute(select(Notification).where(Notification.title == "Approval requested"))).scalars().all()
    assert len(pending) == 20                                              # capped per device
    assert len(notes) == 1                                                 # one note, not thirty
