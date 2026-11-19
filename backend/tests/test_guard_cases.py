"""Phase 3c · C1: cases, not alerts. One person's events become one ranked story; only a high
case notifies, once, without naming anyone; IT closes it, and can make a site quiet."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import AuditLog, GuardCase, Notification
from app.services import guard_cases
from tests.test_browser_policy import _enroll, _guard_on

NOW = datetime.now(UTC)


def _event(minutes_ago=0, **over):
    e = {"at": (NOW - timedelta(minutes=minutes_ago)).isoformat(), "windows_user": r"ACME\ravi",
         "site": "chatgpt.com", "channel": "paste", "mode": "log", "action": "allow",
         "counts": {"Pan": 1}, "contact_list": False, "keyword_hits": 0, "unknown": False}
    return {**e, **over}


def _ev(site="chatgpt.com", action="allow", outcome=None, counts=None, contact_list=False, keyword_hits=0):
    return SimpleNamespace(site=site, action=action, outcome=outcome, counts=counts or {"Pan": 1},
                           contact_list=contact_list, keyword_hits=keyword_hits, channel="paste")


def test_the_score_reads_the_whole_story():
    ignore = {"Email"}
    # One PAN pasted into an AI chat while only recording: low.
    points, level, s = guard_cases.score([_ev()], ignore, set())
    assert level == "low" and s["reasons"] == ["1 PAN", "to chatgpt.com (AI chat)"]
    # 230 PANs to personal file sharing after a warning: high, and the reasons say so.
    points, level, s = guard_cases.score(
        [_ev("wetransfer.com", "warn", "proceeded", {"Pan": 230})], ignore, set())
    assert level == "high" and points >= guard_cases.HIGH
    assert s["reasons"] == ["230 PANs", "to wetransfer.com (personal file sharing)", "went ahead after a warning"]
    # A contact list on a site new to the org: medium; the site is named as new.
    _, level, s = guard_cases.score([_ev("crm-export.io", contact_list=True, counts={"Email": 40})], ignore,
                                    {"crm-export.io"})
    assert level == "medium" and "to crm-export.io (a site new to your organization)" in s["reasons"]
    # E-mail addresses only (ignored by policy), or nothing checkable: not part of any story.
    assert guard_cases.score([_ev(counts={"Email": 9})], ignore, set())[2]["events"] == 0
    # Hidden by redaction counts for little; several places add up.
    # C2: a file downloaded from another system weighs more and is named; the same site is not "moving".
    plain = guard_cases.score([_ev("wetransfer.com", counts={"Pan": 50})], ignore, set())[0]
    moved, _, s = guard_cases.score([SimpleNamespace(**vars(_ev("wetransfer.com", counts={"Pan": 50})),
                                                     origin="crm.zoho.com")], ignore, set())
    same_points, _, same = guard_cases.score([SimpleNamespace(**vars(_ev("wetransfer.com", counts={"Pan": 50})),
                                                              origin="dl.wetransfer.com")], ignore, set())
    assert moved == round(plain * 1.5) and "files downloaded from crm.zoho.com" in s["reasons"]
    assert s["sites"][0]["origins"] == ["crm.zoho.com"]
    assert same_points == plain and not any("downloaded" in r for r in same["reasons"])
    # C3b: a copy to a USB drive is as risky as personal file sharing, and says so in plain words.
    usb_points, _, usb = guard_cases.score([_ev("usb", counts={"Pan": 50})], ignore, set())
    assert usb_points == plain and usb["reasons"] == ["50 PANs", "copied to a USB drive"]
    hidden = guard_cases.score([_ev(action="redact", counts={"Pan": 20})], ignore, set())[0]
    spread = guard_cases.score([_ev(), _ev("claude.ai"), _ev("gemini.google.com")], ignore, set())
    assert hidden < 5 and "across 3 sites" in spread[2]["reasons"]


async def test_events_become_one_case_and_only_a_high_one_notifies(client, admin_headers, user_headers,
                                                                   session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers, "RAVI-PC")
    low = [_event(30), _event(20)]
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": low})).status_code == 204
    r = (await client.get("/api/v1/guard/cases", headers=admin_headers)).json()
    case = r["cases"][0]
    assert len(r["cases"]) == 1 and case["windows_user"] == r"ACME\ravi" and case["devices"] == ["RAVI-PC"]
    assert case["level"] == "low" and case["events"] == 2 and r["open"] == {"high": 0, "medium": 0, "low": 1}
    async with session_factory() as s:
        assert (await s.execute(select(Notification))).scalars().first() is None   # low: no noise

    # The same person keeps going: the same case grows, and turns high once.
    big = [_event(10, site="wetransfer.com", channel="file", mode="warn", action="warn", outcome="proceeded",
                  counts={"Pan": 230}, contact_list=True, origin="crm.zoho.com")]
    bad_origin = [{**big[0], "origin": "crm.zoho.com/export/clients.csv"}]
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": bad_origin})).status_code == 422
    for _ in range(2):
        await client.post("/api/v1/agent/guard/events", headers=h, json={"events": big})
    r = (await client.get("/api/v1/guard/cases", headers=admin_headers)).json()
    case = r["cases"][0]
    assert len(r["cases"]) == 1 and case["level"] == "high" and case["sites"][0]["site"] == "wetransfer.com"
    assert case["sites"][0]["origins"] == ["crm.zoho.com"] and "files downloaded from crm.zoho.com" in case["reasons"]
    events = (await client.get("/api/v1/guard/events", headers=admin_headers)).json()
    assert {e["origin"] for e in events} == {None, "crm.zoho.com"}
    async with session_factory() as s:
        notes = (await s.execute(select(Notification))).scalars().all()
    assert len(notes) == 1 and notes[0].link == "/guard/cases"
    assert "ravi" not in notes[0].message.lower() and "RAVI-PC" not in notes[0].message   # seen by everyone

    # C3b: the agent's USB copy events are taken and join the same person's case.
    usb = [_event(5, site="usb", channel="usb", counts={"Aadhaar": 40})]
    assert (await client.post("/api/v1/agent/guard/events", headers=h, json={"events": usb})).status_code == 204
    case = (await client.get("/api/v1/guard/cases", headers=admin_headers)).json()["cases"][0]
    assert "copied to a USB drive" in case["reasons"] and len(case["sites"]) == 3
    assert next(s for s in case["sites"] if s["site"] == "usb")["new"] is False

    # Cases name people: admins only.
    assert (await client.get("/api/v1/guard/cases", headers=user_headers)).status_code == 403


async def test_closing_quiet_sites_and_a_new_case_after_a_gap(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers, "ASHA-PC")
    asha = r"ACME\asha"
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [
        _event(60 * 72, windows_user=asha, site="files.partner.in", counts={"Pan": 40})]})
    case = (await client.get("/api/v1/guard/cases", headers=admin_headers)).json()["cases"][0]

    # Quiet for more than two days, then more: a new case, the old one left as it was.
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [_event(5, windows_user=asha)]})
    cases = (await client.get("/api/v1/guard/cases", headers=admin_headers)).json()["cases"]
    assert len(cases) == 2 and {c["id"] for c in cases} >= {case["id"]}

    # Only a site in the case, and only when closed as expected, can be made quiet.
    bad = {"resolution": "handled", "quiet_site": "files.partner.in"}
    assert (await client.post(f"/api/v1/guard/cases/{case['id']}/close", headers=admin_headers, json=bad)).status_code == 409
    bad = {"resolution": "expected", "quiet_site": "elsewhere.com"}
    assert (await client.post(f"/api/v1/guard/cases/{case['id']}/close", headers=admin_headers, json=bad)).status_code == 409
    ok = {"resolution": "expected", "quiet_site": "files.partner.in"}
    closed = (await client.post(f"/api/v1/guard/cases/{case['id']}/close", headers=admin_headers, json=ok)).json()
    assert closed["status"] == "closed" and closed["resolution"] == "expected"
    assert (await client.post(f"/api/v1/guard/cases/{case['id']}/close", headers=admin_headers, json=ok)).status_code == 409

    # The quiet site no longer raises cases, but its events are kept, counted and shown.
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [
        _event(1, windows_user=asha, site="files.partner.in", counts={"Pan": 400})]})
    r = (await client.get("/api/v1/guard/cases", headers=admin_headers)).json()
    assert r["quiet_sites"] == ["files.partner.in"] and r["quiet_events_30d"] == 2   # both, in 30 days
    assert all(s["site"] != "files.partner.in" for c in r["cases"] for s in c["sites"])
    events = (await client.get("/api/v1/guard/events", headers=admin_headers)).json()
    assert any(e["site"] == "files.partner.in" for e in events)
    closed_list = (await client.get("/api/v1/guard/cases?status=closed", headers=admin_headers)).json()["cases"]
    assert [c["id"] for c in closed_list] == [case["id"]]

    assert (await client.delete("/api/v1/guard/quiet-sites/files.partner.in", headers=admin_headers)).status_code == 204
    assert (await client.delete("/api/v1/guard/quiet-sites/files.partner.in", headers=admin_headers)).status_code == 404
    async with session_factory() as s:
        actions = [a.action for a in (await s.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars()]
        assert "guard.case_close" in actions and "guard.quiet_site_remove" in actions
        assert len((await s.execute(select(GuardCase))).scalars().all()) == 2
