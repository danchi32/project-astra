"""Phase 3 · E3: browser extension events, counts only, from the agent to the admin."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import GuardEvent
from tests.test_browser_policy import _enroll, _guard_on


def _event(**over):
    e = {"at": datetime.now(UTC).isoformat(), "windows_user": r"PC-1\asha", "site": "chatgpt.com",
         "channel": "paste", "mode": "warn", "action": "warn", "counts": {"Pan": 2, "Email": 0},
         "contact_list": False, "keyword_hits": 1, "unknown": False}
    return {**e, **over}


async def test_events_are_stored_and_summarised(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers, "GUARD-PC")
    batch = {"events": [
        _event(),
        _event(site="claude.ai", action="block", mode="block", counts={"Aadhaar": 1}, keyword_hits=0),
        _event(windows_user=r"PC-1\ravi", counts={}, keyword_hits=0, contact_list=True),
        _event(unknown=True, counts={}, keyword_hits=0),
        _event(at=(datetime.now(UTC) + timedelta(days=2)).isoformat()),          # clock error: dropped
    ]}
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json=batch)).status_code == 204

    s = (await client.get("/api/v1/guard/events/summary?days=7", headers=admin_headers)).json()
    assert (s["total"], s["warned"], s["blocked"], s["unknown"]) == (4, 3, 1, 1)
    assert s["kinds"] == {"Pan": 1, "Aadhaar": 1}            # events with each kind; zero counts dropped
    assert s["contact_lists"] == 1 and s["keyword_events"] == 1
    assert s["top_sites"][0] == {"site": "chatgpt.com", "events": 3}
    assert s["top_people"][0] == {"windows_user": r"PC-1\asha", "events": 3}

    rows = (await client.get("/api/v1/guard/events?limit=2", headers=admin_headers)).json()
    assert len(rows) == 2 and rows[0]["hostname"] == "GUARD-PC"


async def test_the_schema_is_fixed(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    for bad in (_event(text="ABCPE1234F"),                       # no free text, however named
                _event(site="chatgpt.com/c/123"), _event(site="My notes"),
                _event(channel="print"), _event(counts={"Password": 1}),
                _event(windows_user="a\nb"), _event(keyword_hits=999),
                # Review M1: an account name, never a message to the admin, and no invisible text.
                _event(windows_user="IT Security: your account is locked, call +1-555-0100"),
                _event(windows_user="PC-1\\asha\u202egnp.exe"), _event(windows_user="PC-1\\as\u200bha")):
        r = await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [bad]})
        assert r.status_code == 422, bad
    r = await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [_event()] * 501})
    assert r.status_code == 422


async def test_answers_to_prompts(client, admin_headers, session_factory, admin_user):
    """D7: whether the person went ahead after a warn / justify prompt, and why, as a code."""
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    j = {"mode": "justify", "action": "justify"}
    ok = [_event(**j, outcome="proceeded", reason="client_request"), _event(**j, outcome="proceeded", reason="approved"),
          _event(**j, outcome="cancelled"), _event(outcome="proceeded")]
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": ok})).status_code == 204

    s = (await client.get("/api/v1/guard/events/summary", headers=admin_headers)).json()
    assert (s["justified"], s["warned"], s["went_ahead"], s["stopped"]) == (3, 1, 3, 1)
    assert s["reasons"] == {"client_request": 1, "approved": 1}
    rows = (await client.get("/api/v1/guard/events", headers=admin_headers)).json()
    assert {(r["outcome"], r["reason"]) for r in rows} >= {("proceeded", "client_request"), ("cancelled", None)}

    r = {"mode": "redact", "action": "redact"}
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [_event(**r)]})).status_code == 204
    assert (await client.get("/api/v1/guard/events/summary", headers=admin_headers)).json()["redacted"] == 1

    for bad in (_event(**r, outcome="proceeded"),                         # a redacted paste has no answer
                _event(**j, outcome="proceeded"),                         # justify needs a reason
                _event(**j, outcome="proceeded", reason="I felt like it"),  # never free text
                _event(outcome="cancelled", reason="approved"),
                _event(action="block", mode="block", outcome="proceeded"),
                _event(reason="approved")):
        assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [bad]})).status_code == 422, bad


async def test_without_the_add_on_events_are_dropped(client, admin_headers, session_factory, admin_user):
    _, h = await _enroll(client, admin_headers)
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [_event()]})).status_code == 204
    async with session_factory() as s:
        assert (await s.execute(select(GuardEvent))).scalars().first() is None
    assert (await client.get("/api/v1/guard/events/summary", headers=admin_headers)).status_code == 402


async def test_only_admins_read_events(client, admin_headers, session_factory, admin_user, org):
    from app.models import UserRole
    from tests.conftest import _create_user, auth_headers

    await _guard_on(session_factory, admin_user.org_id)
    await _create_user(session_factory, org.id, "tech@acme.com", "TechPassw0rd!2345", UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", "TechPassw0rd!2345")
    assert (await client.get("/api/v1/guard/events", headers=tech)).status_code == 403
    assert (await client.get("/api/v1/guard/events/summary", headers=tech)).status_code == 403


async def test_old_events_are_pruned(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    device_id, h = await _enroll(client, admin_headers)
    async with session_factory() as s:
        s.add(GuardEvent(org_id=admin_user.org_id, device_id=device_id, windows_user="x", site="a.in",
                         channel="paste", mode="log", action="allow", counts={"Pan": 1},
                         occurred_at=datetime.now(UTC) - timedelta(days=200)))
        await s.commit()
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [_event()]})
    async with session_factory() as s:
        sites = [e.site for e in (await s.execute(select(GuardEvent))).scalars()]
    assert sites == ["chatgpt.com"]


async def test_old_events_and_floods_are_not_taken(client, admin_headers, session_factory, admin_user, monkeypatch):
    """Review M2: events older than two weeks are dropped, and one PC is taken at most a day's cap."""
    from app.services import guard_events

    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    monkeypatch.setattr(guard_events, "DAILY_CAP", 3)
    old = _event(at=(datetime.now(UTC) - timedelta(days=20)).isoformat())
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [old] + [_event()] * 5})
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [_event()]})
    async with session_factory() as s:
        assert len((await s.execute(select(GuardEvent))).scalars().all()) == 3
