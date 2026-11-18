"""Phase 3 · D5 slice 2: suggestions come from the org's own evidence, say why, change exactly
what they say, go through the audited policy update, and can be dismissed for good."""
from sqlalchemy import select

from app.models import AuditLog
from tests.test_browser_policy import _enroll, _guard_on
from tests.test_guard_discovery import _map
from tests.test_guard_events import _event

EXT = "abcdefghijklmnopabcdefghijklmnop"


async def _setup(client, admin_headers, session_factory, admin_user, policy=None, events=(), discovery=None):
    await _guard_on(session_factory, admin_user.org_id)
    if policy is not None:
        r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=policy)
        assert r.status_code == 200, r.text
    _, h = await _enroll(client, admin_headers)
    if events:
        await client.post("/api/v1/agent/guard/events", headers=h, json={"events": list(events)})
    if discovery:
        await client.post("/api/v1/agent/guard/discovery", headers=h, json=discovery)


async def _keys(client, h):
    return {s["key"]: s for s in (await client.get("/api/v1/guard/suggestions", headers=h)).json()}


async def test_nothing_seen_nothing_suggested(client, admin_headers, session_factory, admin_user):
    await _setup(client, admin_headers, session_factory, admin_user)
    assert await _keys(client, admin_headers) == {}


async def test_evidence_drives_each_rule(client, admin_headers, session_factory, admin_user):
    ai = [_event(site="chatgpt.com", mode="log", action="allow")] * 3
    other = [_event(site="mail.example.com", mode="log", action="allow", contact_list=True)]
    await _setup(client, admin_headers, session_factory, admin_user,
                 policy={"chrome_extension_id": EXT, "guard_watched_sites": ["intranet.acme.in"]},
                 events=ai + other, discovery=_map())
    # E8: during the pilot recording is the point, so no card asks to stop recording.
    assert "leave_record_only" not in await _keys(client, admin_headers)
    await client.post("/api/v1/guard/browser-policy/end-pilot", headers=admin_headers)
    s = await _keys(client, admin_headers)
    assert set(s) == {"leave_record_only", "block_file_sharing", "no_private_windows",
                      "no_unpacked_extensions", "watch_ai_sites", "find_files"}
    assert s["leave_record_only"]["changes"] == ["Mode: Hide the sensitive parts"]     # 3 of 4 on AI chat sites
    assert "pasted or uploaded 4 times" in s["leave_record_only"]["why"] and "3 of them on AI chat sites" in s["leave_record_only"]["why"]
    assert "3 contact lists" in s["block_file_sharing"]["why"]                           # 2 in files + 1 pasted
    assert "patch" not in s["block_file_sharing"]                                        # the API shows words, not internals


async def test_apply_changes_exactly_that_and_is_audited(client, admin_headers, session_factory, admin_user):
    await _setup(client, admin_headers, session_factory, admin_user,
                 policy={"blocked_sites": ["example.com"]}, discovery=_map())
    s = await _keys(client, admin_headers)
    assert set(s) == {"block_file_sharing"}
    shown = s["block_file_sharing"]["changes"]
    stale = await client.post("/api/v1/guard/suggestions/block_file_sharing/apply", headers=admin_headers,
                              json={"changes": ["Block something else"]})
    assert stale.status_code == 409                                                       # review L3
    r = await client.post("/api/v1/guard/suggestions/block_file_sharing/apply", headers=admin_headers,
                          json={"changes": shown})
    assert r.status_code == 200, r.text
    p = r.json()["policy"]
    assert p["blocked_sites"][0] == "example.com" and "wetransfer.com" in p["blocked_sites"]   # added to, not replaced
    assert r.json()["version"] == 2
    assert await _keys(client, admin_headers) == {}                                      # condition gone, so is the card
    async with session_factory() as db:
        actions = {a.action for a in (await db.execute(select(AuditLog))).scalars()}
    assert {"guard.suggestion_apply", "guard.browser_policy_update"} <= actions
    again = await client.post("/api/v1/guard/suggestions/block_file_sharing/apply", headers=admin_headers,
                              json={"changes": shown})
    assert again.status_code == 404


async def test_dismiss_for_good_and_roles(client, admin_headers, session_factory, admin_user, org):
    from app.models import UserRole
    from tests.conftest import _create_user, auth_headers

    await _setup(client, admin_headers, session_factory, admin_user, policy={"chrome_extension_id": EXT})
    assert "no_private_windows" in await _keys(client, admin_headers)
    await _create_user(session_factory, org.id, "tech@acme.com", "TechPassw0rd!2345", UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", "TechPassw0rd!2345")
    assert (await client.get("/api/v1/guard/suggestions", headers=tech)).status_code == 403
    body = {"changes": ["No incognito / InPrivate / private windows"]}
    assert (await client.post("/api/v1/guard/suggestions/no_private_windows/apply", headers=tech, json=body)).status_code == 403

    assert (await client.post("/api/v1/guard/suggestions/no_private_windows/dismiss", headers=admin_headers)).status_code == 204
    assert "no_private_windows" not in await _keys(client, admin_headers)
    assert (await client.post("/api/v1/guard/suggestions/no_private_windows/apply", headers=admin_headers, json=body)).status_code == 404
    assert (await client.post("/api/v1/guard/suggestions/made_up/dismiss", headers=admin_headers)).status_code == 404


async def test_apply_that_would_break_the_policy_is_refused(client, admin_headers, session_factory, admin_user):
    """Review L3: adding to a list already at its limit is a 409, not a 500."""
    full = [f"s{i}.example.com" for i in range(500)]
    await _setup(client, admin_headers, session_factory, admin_user, policy={"blocked_sites": full}, discovery=_map())
    s = await _keys(client, admin_headers)
    r = await client.post("/api/v1/guard/suggestions/block_file_sharing/apply", headers=admin_headers,
                          json={"changes": s["block_file_sharing"]["changes"]})
    assert r.status_code == 409
