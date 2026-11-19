"""Phase 3b · I1: breach records — opened from a case or on their own, steps settled with when and
by whom, closed only once every step is settled, every change audited and shown as the timeline.
No legal deadlines: counsel decides, and reporting can be marked not needed on that advice."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditLog, GuardCase, GuardIncident
from tests.test_browser_policy import _guard_on

URL = "/api/v1/guard/incidents"


def _facts(**over):
    return {"title": "Client list sent to a personal Gmail", "what_happened": "Found in case review.\nOne file.",
            "found_at": (datetime.now(UTC) - timedelta(hours=5)).isoformat(), "kinds": ["Pan", "IndianMobile", "Pan"],
            "people_affected": 240, **over}


async def test_a_breach_record_from_open_to_closed(client, admin_headers, user_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    async with session_factory() as s:
        case = GuardCase(org_id=admin_user.org_id, windows_user=r"ACME\ravi", opened_at=datetime.now(UTC),
                         last_event_at=datetime.now(UTC), status="open", score=80, level="high", summary={"sites": {}})
        s.add(case)
        await s.commit()
        case_id = case.id

    for bad in (_facts(title="a\u202eb"), _facts(title="  "), _facts(kinds=["Passwords"]),
                _facts(found_at=(datetime.now(UTC) + timedelta(days=1)).isoformat()), {**_facts(), "x": 1},
                _facts(what_happened="a\u200bb")):
        assert (await client.post(URL, headers=admin_headers, json=bad)).status_code == 422, bad
    assert (await client.post(URL, headers=admin_headers, json={**_facts(), "case_id": str(uuid.uuid4())})).status_code == 404
    assert (await client.post(URL, headers=user_headers, json=_facts())).status_code == 403

    r = await client.post(URL, headers=admin_headers, json={**_facts(), "case_id": str(case_id)})
    assert r.status_code == 201
    inc = r.json()
    assert inc["status"] == "open" and inc["kinds"] == ["Pan", "IndianMobile"] and inc["people_affected"] == 240
    assert [s["key"] for s in inc["steps"]] == ["contain", "assess", "counsel", "board", "people", "fix"]
    assert all(s["state"] is None for s in inc["steps"])
    assert [s["optional"] for s in inc["steps"]] == [False, False, False, True, True, False]
    one = f"{URL}/{inc['id']}"

    # Steps: done with a note and who; only reporting can be "not needed"; closing waits for all.
    r = await client.patch(one, headers=admin_headers, json={"step": {"key": "contain", "state": "done",
                                                                       "note": "Blocked gmail.com for Ravi's PC"}})
    contain = r.json()["steps"][0]
    assert contain["state"] == "done" and contain["by"] == admin_user.full_name and contain["note"].startswith("Blocked")
    assert (await client.patch(one, headers=admin_headers, json={"step": {"key": "counsel", "state": "not_needed"}})
            ).status_code == 422
    assert (await client.patch(one, headers=admin_headers, json={"closed": True})).status_code == 409
    for key, state in (("assess", "done"), ("counsel", "done"), ("board", "not_needed"), ("people", "done"),
                       ("fix", "done")):
        assert (await client.patch(one, headers=admin_headers, json={"step": {"key": key, "state": state}})
                ).status_code == 200
    # Facts can change; only the number of people can be cleared.
    assert (await client.patch(one, headers=admin_headers, json={"title": None})).status_code == 422
    r = await client.patch(one, headers=admin_headers, json={"people_affected": None, "closed": True})
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["closed_at"]
    assert r.json()["people_affected"] is None
    # A step undone reopens nothing by itself; reopening is explicit.
    assert (await client.patch(one, headers=admin_headers, json={"closed": False})).json()["status"] == "open"

    d = (await client.get(one, headers=admin_headers)).json()
    assert d["case"]["windows_user"] == r"ACME\ravi" and d["case"]["level"] == "high"
    assert [t["action"] for t in d["timeline"]][:2] == ["dpdp.incident_open", "dpdp.incident_update"]
    assert len(d["timeline"]) == 1 + 1 + 5 + 1 + 1 and all(t["by"] == admin_user.full_name for t in d["timeline"])
    # Review 3b M2: technicians read the audit log, so it holds which step and field, never the words.
    details = str([t["detail"] for t in d["timeline"]])
    assert "Blocked gmail" not in details and "Client list" not in details and "Found in case" not in details
    assert {"key": "contain", "state": "done"} in [t["detail"].get("step") for t in d["timeline"]]
    assert {"fields": ["people_affected"], "status": "closed"} in [t["detail"] for t in d["timeline"]]
    assert (await client.get(URL, headers=admin_headers)).json()[0]["id"] == inc["id"]
    assert (await client.get(one, headers=user_headers)).status_code == 403

    # Another organisation's record does not exist from here.
    async with session_factory() as s:
        other = GuardIncident(org_id=uuid.uuid4(), title="x", what_happened="", found_at=datetime.now(UTC), kinds=[],
                              status="open", steps={}, opened_at=datetime.now(UTC))
        s.add(other)
        await s.commit()
        assert await s.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.target_type == "guard_incident")) == len(d["timeline"])
    assert (await client.get(f"{URL}/{other.id}", headers=admin_headers)).status_code == 404
    assert (await client.patch(f"{URL}/{other.id}", headers=admin_headers, json={"closed": True})).status_code == 404
    assert len((await client.get(URL, headers=admin_headers)).json()) == 1
