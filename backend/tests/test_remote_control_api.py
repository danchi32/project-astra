"""The endpoints, and the one rule that shapes them.

A viewer URL is a credential — it logs its bearer into the relay as the technician and
puts them on a named device. So most of what is asserted here is about who does NOT get
one: not before consent, not a colleague, and never from the list endpoint.
"""
import pytest
from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import (
    AuditLog,
    Device,
    Organization,
    RemoteSession,
    RemoteSessionStatus,
    User,
)
from app.models.base import utcnow
from app.services.entitlements import REMOTE_CONTROL
from app.services.remote_control import RemoteControlService

REASON = "Excel freezes every time they open the shared workbook"
NODE = "node//api-test-node"


async def _grant(session_factory, org, on=True):
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.entitlement_overrides = {REMOTE_CONTROL: on}
        await s.commit()


async def _device(session_factory, org, machine="api-1", node_id=NODE):
    async with session_factory() as s:
        device = Device(
            org_id=org.id, hostname="API-PC", machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
            meshcentral_node_id=node_id,
        )
        s.add(device)
        await s.commit()
        return str(device.id)


# ── The plan gate ─────────────────────────────────────────────────────────


async def test_an_org_below_expert_is_told_to_upgrade_not_refused(
    client, session_factory, org, admin_headers
):
    """402, not 403. The caller has the right role; their plan simply doesn't include
    this — it is Expert-only — and "ask your administrator" and "upgrade" are different
    next steps."""
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.plan = "professional"        # everything but the top tier
        await s.commit()

    device_id = await _device(session_factory, org, "api-gate")
    r = await client.post("/api/v1/remote-sessions", headers=admin_headers,
                          json={"device_id": device_id, "reason": REASON})
    assert r.status_code == 402, r.text
    assert r.headers.get("X-Astra-Required-Feature") == REMOTE_CONTROL


# ── Requesting ────────────────────────────────────────────────────────────


async def test_a_request_starts_pending_with_a_countdown(
    client, session_factory, org, admin_headers
):
    """The portal is told how long the person has, by the server that enforces it.

    No relay is configured here, so there is no link either — that is this deployment
    having no relay, NOT a rule about pending sessions. The rule is the opposite, and it
    has its own test below.
    """
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-2")

    r = await client.post("/api/v1/remote-sessions", headers=admin_headers,
                          json={"device_id": device_id, "reason": REASON})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["viewer_url"] is None        # no relay on this deployment
    assert 0 < body["expires_in_seconds"] <= 120
    assert body["device_hostname"] == "API-PC"
    assert body["requested_by_name"]


@pytest.mark.parametrize("reason", ["", "too short"])
async def test_a_request_without_a_real_reason_is_rejected_by_field(
    client, session_factory, org, admin_headers, reason
):
    """422 naming `reason`, so the portal can put the message under the box."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, f"api-r{len(reason)}")
    r = await client.post("/api/v1/remote-sessions", headers=admin_headers,
                          json={"device_id": device_id, "reason": reason})
    assert r.status_code == 422, r.text
    assert "reason" in r.text


async def test_a_second_request_on_a_busy_device_is_a_conflict(
    client, session_factory, org, admin_headers
):
    """409, not 400. A plain error invites a second click, and a second click puts a
    second consent prompt on somebody's screen."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-3")
    body = {"device_id": device_id, "reason": REASON}

    assert (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                              json=body)).status_code == 201
    r = await client.post("/api/v1/remote-sessions", headers=admin_headers, json=body)
    assert r.status_code == 409, r.text


async def test_a_regular_user_cannot_request_a_session(
    client, session_factory, org, user_headers
):
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-4")
    r = await client.post("/api/v1/remote-sessions", headers=user_headers,
                          json={"device_id": device_id, "reason": REASON})
    assert r.status_code == 403, r.text


async def test_a_device_in_another_org_is_not_found(
    client, session_factory, org, other_org, admin_headers
):
    await _grant(session_factory, org)
    await _grant(session_factory, other_org)
    theirs = await _device(session_factory, other_org, "api-5", "node//theirs")
    r = await client.post("/api/v1/remote-sessions", headers=admin_headers,
                          json={"device_id": theirs, "reason": REASON})
    assert r.status_code == 404, r.text


# ── The viewer link ───────────────────────────────────────────────────────


async def test_the_link_is_issued_while_pending_because_it_is_what_asks(
    client, session_factory, org, admin_headers, monkeypatch
):
    """This test used to assert the opposite, and it was wrong in a way worth recording.

    "No link until they agree" reads like the safe rule. It deadlocks: opening the viewer
    is what puts the prompt on the person's screen, so with no link nothing ever asks,
    nothing is ever approved, and no link is ever issued. The feature could not complete a
    single session.

    Consent is enforced by the relay, which holds the stream until the person allows it —
    a gate that can actually stop pixels. Withholding the link only stopped the question,
    while looking like security.
    """
    _relay(monkeypatch)
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-6")

    created = (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                                 json={"device_id": device_id, "reason": REASON})).json()
    assert created["status"] == "pending"
    assert created["viewer_url"], "a pending session must carry the link that asks"

    r = await client.get(f"/api/v1/remote-sessions/{created['id']}", headers=admin_headers)
    assert r.json()["viewer_url"]


async def test_no_link_is_issued_after_a_refusal(
    client, session_factory, org, admin_headers, monkeypatch
):
    """Still true, and now for the right reason: with a relay configured, a pending
    session WOULD carry a link, so its absence here is the refusal and nothing else."""
    _relay(monkeypatch)
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-7")
    created = (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                                 json={"device_id": device_id, "reason": REASON})).json()

    async with session_factory() as s:
        await RemoteControlService(s).record_response(
            session_id=created["id"], accepted=False)

    r = await client.get(f"/api/v1/remote-sessions/{created['id']}", headers=admin_headers)
    assert r.json()["status"] == "declined"
    assert r.json()["viewer_url"] is None


async def test_the_list_endpoint_never_carries_links(
    client, session_factory, org, admin_headers, monkeypatch
):
    """A list is read by a page showing many sessions to whoever can open the page.
    Minting credentials into it would scatter them."""
    _relay(monkeypatch)
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-8")
    created = (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                                 json={"device_id": device_id, "reason": REASON})).json()
    async with session_factory() as s:
        await RemoteControlService(s).record_response(
            session_id=created["id"], accepted=True)

    r = await client.get("/api/v1/remote-sessions", headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all(i["viewer_url"] is None for i in items)


async def test_a_colleague_cannot_pick_up_someone_elses_link(
    client, session_factory, org, admin_user, admin_headers, monkeypatch
):
    """Another technician in the same org can SEE the session — it is their org's
    record — but handing them the link would hand them the session itself."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-9")
    created = (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                                 json={"device_id": device_id, "reason": REASON})).json()
    async with session_factory() as s:
        await RemoteControlService(s).record_response(
            session_id=created["id"], accepted=True)

    # A second technician in the same org.
    from app.core.security import hash_password
    from app.models import UserRole
    async with session_factory() as s:
        s.add(User(org_id=org.id, email="tech2@example.com", full_name="Second Tech",
                   hashed_password=hash_password("TechPassw0rd!2345"),
                   role=UserRole.TECHNICIAN, is_active=True))
        await s.commit()
    login = await client.post("/api/v1/auth/login",
                              json={"email": "tech2@example.com",
                                    "password": "TechPassw0rd!2345"})
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.get(f"/api/v1/remote-sessions/{created['id']}", headers=other)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert r.json()["viewer_url"] is None


async def test_a_session_from_another_org_is_not_found(
    client, session_factory, org, other_org, admin_headers
):
    """An ADMIN of another org — so the role and plan gates both pass, and what refuses
    them is org isolation itself rather than something in front of it."""
    await _grant(session_factory, org)
    await _grant(session_factory, other_org)
    device_id = await _device(session_factory, org, "api-10")
    created = (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                                 json={"device_id": device_id, "reason": REASON})).json()

    from app.core.security import hash_password
    from app.models import UserRole
    async with session_factory() as s:
        s.add(User(org_id=other_org.id, email="admin@other.example.com",
                   full_name="Other Admin",
                   hashed_password=hash_password("OtherPassw0rd!234"),
                   role=UserRole.ADMIN, is_active=True))
        await s.commit()
    login = await client.post("/api/v1/auth/login",
                              json={"email": "admin@other.example.com",
                                    "password": "OtherPassw0rd!234"})
    assert login.status_code == 200, login.text
    theirs = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.get(f"/api/v1/remote-sessions/{created['id']}", headers=theirs)
    assert r.status_code == 404, r.text


# ── Ending ────────────────────────────────────────────────────────────────


async def test_ending_twice_is_not_an_error(
    client, session_factory, org, admin_headers
):
    """Both sides can hang up at once. Neither should see a failure, and the record must
    show one ending, not two."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-11")
    created = (await client.post("/api/v1/remote-sessions", headers=admin_headers,
                                 json={"device_id": device_id, "reason": REASON})).json()

    first = await client.post(f"/api/v1/remote-sessions/{created['id']}/end",
                              headers=admin_headers)
    second = await client.post(f"/api/v1/remote-sessions/{created['id']}/end",
                               headers=admin_headers)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["status"] == "ended"

    async with session_factory() as s:
        ends = [a for a in (await s.execute(select(AuditLog.action))).scalars().all()
                if a == "remote_session.end"]
        assert len(ends) == 1, ends


async def test_the_whole_request_is_audited(client, session_factory, org, admin_headers):
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "api-12")
    await client.post("/api/v1/remote-sessions", headers=admin_headers,
                      json={"device_id": device_id, "reason": REASON})

    async with session_factory() as s:
        rows = (await s.execute(
            select(AuditLog.action, AuditLog.detail))).all()
        req = next(d for a, d in rows if a == "remote_session.request")
        # The technician's words are in the trail, because "why did you connect to my
        # machine on Tuesday" is the question this record exists to answer.
        assert req["reason"] == REASON


# ── Listing ───────────────────────────────────────────────────────────────


async def test_sessions_can_be_filtered_by_device_and_status(
    client, session_factory, org, admin_headers
):
    await _grant(session_factory, org)
    a = await _device(session_factory, org, "api-13a", "node//a")
    b = await _device(session_factory, org, "api-13b", "node//b")
    for dev in (a, b):
        await client.post("/api/v1/remote-sessions", headers=admin_headers,
                          json={"device_id": dev, "reason": REASON})

    r = await client.get(f"/api/v1/remote-sessions?device_id={a}", headers=admin_headers)
    assert r.json()["total"] == 1

    r = await client.get("/api/v1/remote-sessions?status=pending", headers=admin_headers)
    assert r.json()["total"] == 2
    r = await client.get("/api/v1/remote-sessions?status=declined", headers=admin_headers)
    assert r.json()["total"] == 0


async def test_another_orgs_sessions_are_not_listed(
    client, session_factory, org, other_org, admin_headers
):
    await _grant(session_factory, org)
    await _grant(session_factory, other_org)
    mine = await _device(session_factory, org, "api-14", "node//mine")
    await client.post("/api/v1/remote-sessions", headers=admin_headers,
                      json={"device_id": mine, "reason": REASON})

    theirs_device = await _device(session_factory, other_org, "api-15", "node//theirs2")
    async with session_factory() as s:
        device = await s.get(Device, __import__("uuid").UUID(theirs_device))
        s.add(RemoteSession(
            org_id=other_org.id, device_id=device.id,
            requested_by_user_id=device.id,  # any uuid; not read by the listing
            reason="their problem", status=RemoteSessionStatus.PENDING,
            requested_at=utcnow(),
        ))
        await s.commit()

    r = await client.get("/api/v1/remote-sessions", headers=admin_headers)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["reason"] == REASON


def _relay(monkeypatch):
    """A relay that does not exist. Nothing here connects to one — issuing a viewer link
    is pure composition — but without it `viewer_url` is empty for a reason that has
    nothing to do with what these tests are checking."""
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "meshcentral_url", "https://relay.test", raising=False)
    monkeypatch.setattr(s, "meshcentral_user", "~t:test", raising=False)
    monkeypatch.setattr(s, "meshcentral_token", "test-token", raising=False)
    monkeypatch.setattr(s, "meshcentral_cookie_key", "ab" * 80, raising=False)
    # Pin the user id so resolve_user_id needs no relay round-trip in tests.
    monkeypatch.setattr(s, "meshcentral_user_id", "user//test", raising=False)
