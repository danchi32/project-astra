"""Workforce Insights ("Tracker") — Phase 1 attendance.

Two layers: the pure span builder (no DB, so the time logic is pinned directly), and the
real path agent push → aggregation → portal read, including the entitlement gate that is the
whole point of a monitoring feature.
"""
from datetime import date, datetime, timezone

from app.services.workforce import _summarize, build_work_spans

UTC = timezone.utc
DAY = date(2026, 7, 7)
# A "now" on a LATER day, so DAY is treated as finished (not the ongoing-today path).
NOW_PAST = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)


def _dt(hour, minute=0, d=7):
    return datetime(2026, 7, d, hour, minute, tzinfo=UTC)


# ── The span builder (pure) ──────────────────────────────────────────────────


def test_a_plain_day_is_one_span():
    spans = build_work_spans(
        [("logon", _dt(9)), ("logoff", _dt(17))], day=DAY, now=NOW_PAST, seed_present=False
    )
    assert len(spans) == 1
    assert _summarize(spans, day=DAY, now=NOW_PAST) == (_dt(9), _dt(17), 480)


def test_a_lock_opens_a_break():
    events = [("logon", _dt(9)), ("lock", _dt(12)), ("unlock", _dt(12, 30)), ("logoff", _dt(17, 30))]
    spans = build_work_spans(events, day=DAY, now=NOW_PAST, seed_present=False)
    assert len(spans) == 2
    first_in, last_out, worked = _summarize(spans, day=DAY, now=NOW_PAST)
    # 3h + 5h = 8h, the 30-minute lock is NOT worked time.
    assert (first_in, last_out, worked) == (_dt(9), _dt(17, 30), 480)


def test_still_signed_in_today_counts_up_to_now_and_has_no_last_out():
    now = datetime(2026, 7, 7, 13, 0, tzinfo=UTC)   # same day as DAY => ongoing
    spans = build_work_spans([("logon", _dt(9))], day=DAY, now=now, seed_present=False)
    assert spans[-1].ended_at is None
    first_in, last_out, worked = _summarize(spans, day=DAY, now=now)
    assert first_in == _dt(9)
    assert last_out is None          # still in
    assert worked == 240             # 09:00 → now (13:00)


def test_presence_carried_over_midnight_starts_at_day_start():
    # Last transition before the day was a logon (seed_present), and they lock at 02:00.
    spans = build_work_spans([("lock", _dt(2))], day=DAY, now=NOW_PAST, seed_present=True)
    assert len(spans) == 1
    assert spans[0].started_at == _dt(0)
    assert spans[0].ended_at == _dt(2)


def test_a_full_day_of_carried_over_presence_with_no_events_counts_whole_day():
    spans = build_work_spans([], day=DAY, now=NOW_PAST, seed_present=True)
    assert len(spans) == 1
    assert spans[0].started_at == _dt(0)
    assert spans[0].ended_at == _dt(0, 0, d=8)      # next midnight
    assert _summarize(spans, day=DAY, now=NOW_PAST)[2] == 1440


def test_a_missing_logoff_on_a_past_day_never_fabricates_hours():
    # A lone logon with no close on a finished day: conservative — no worked time invented.
    spans = build_work_spans([("logon", _dt(9))], day=DAY, now=NOW_PAST, seed_present=False)
    assert spans == []
    assert _summarize(spans, day=DAY, now=NOW_PAST) is None


# ── The real path: agent push → aggregation → portal read ─────────────────────

TELEMETRY_PAYLOAD = {
    "collected_at": "2026-07-07T18:00:00Z",
    "cpu_percent": 10.0,
    "ram_total_mb": 16384,
    "ram_used_mb": 4096,
    "disks": [{"drive": "C:", "total_gb": 500.0, "used_gb": 100.0, "free_gb": 400.0}],
}

ACTIVITY = [
    {"username": "ACME\\rahul", "kind": "logon", "occurred_at": "2026-07-07T09:00:00Z"},
    {"username": "ACME\\rahul", "kind": "lock", "occurred_at": "2026-07-07T12:00:00Z"},
    {"username": "ACME\\rahul", "kind": "unlock", "occurred_at": "2026-07-07T12:30:00Z"},
    {"username": "ACME\\rahul", "kind": "logoff", "occurred_at": "2026-07-07T17:30:00Z"},
]


async def _enable_tracker(session_factory, org_id):
    from app.models import Organization
    from app.services.entitlements import WORKFORCE_INSIGHTS

    async with session_factory() as session:
        org = await session.get(Organization, org_id)
        org.entitlement_overrides = {WORKFORCE_INSIGHTS: True}
        await session.commit()


async def _enroll_device(client, admin_headers):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens",
        json={"name": "tracker-test"},
        headers=admin_headers,
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": "TRK-PC-001",
            "machine_id": "trk-machine",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return enroll.json()["device_token"]


async def _push(client, device_token, payload):
    return await client.post(
        "/api/v1/agent/telemetry",
        json=payload,
        headers={"Authorization": f"Bearer {device_token}"},
    )


async def test_attendance_is_gated_by_the_entitlement(client, admin_headers):
    """Default plan already resolves to Expert, yet the Tracker is OFF — it lives in no tier
    and arrives only by a deliberate per-org override. 402, not 403: the role is fine."""
    resp = await client.get("/api/v1/tracker/attendance", headers=admin_headers)
    assert resp.status_code == 402, resp.text
    assert resp.headers.get("X-Astra-Required-Feature") == "workforce_insights"


async def test_push_to_portal_attendance(client, admin_headers, admin_user, session_factory):
    await _enable_tracker(session_factory, admin_user.org_id)
    device_token = await _enroll_device(client, admin_headers)
    assert (await _push(client, device_token, {**TELEMETRY_PAYLOAD, "activity": ACTIVITY})).status_code == 200

    resp = await client.get(
        "/api/v1/tracker/attendance",
        params={"from": "2026-07-07", "to": "2026-07-07"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["username"] == "ACME\\rahul"
    assert row["device_hostname"] == "TRK-PC-001"
    assert row["worked_minutes"] == 480          # 8h, lock excluded
    assert row["first_in"].startswith("2026-07-07T09:00")
    assert row["last_out"].startswith("2026-07-07T17:30")
    # P1 does not measure these — they must read as "unknown", not a measured 0.
    assert row["active_minutes"] is None
    assert row["productive_minutes"] is None


async def test_the_spans_behind_a_day_are_readable(client, admin_headers, admin_user, session_factory):
    await _enable_tracker(session_factory, admin_user.org_id)
    device_token = await _enroll_device(client, admin_headers)
    await _push(client, device_token, {**TELEMETRY_PAYLOAD, "activity": ACTIVITY})
    device_id = (await client.get("/api/v1/devices", headers=admin_headers)).json()[0]["id"]

    resp = await client.get(
        "/api/v1/tracker/attendance/sessions",
        params={"device_id": device_id, "username": "ACME\\rahul", "day": "2026-07-07"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    spans = resp.json()
    assert len(spans) == 2
    assert spans[0]["started_at"].startswith("2026-07-07T09:00")
    assert spans[0]["ended_at"].startswith("2026-07-07T12:00")


async def test_activity_is_dropped_when_the_org_is_not_entitled(
    client, admin_headers, admin_user, session_factory
):
    """The push still succeeds — a telemetry beat is never failed over this — but the activity
    is NOT collected. Enabling the Tracker afterwards must not surface data from before it was
    on: the safe failure for monitoring data is to not collect it."""
    device_token = await _enroll_device(client, admin_headers)
    assert (await _push(client, device_token, {**TELEMETRY_PAYLOAD, "activity": ACTIVITY})).status_code == 200

    await _enable_tracker(session_factory, admin_user.org_id)
    resp = await client.get(
        "/api/v1/tracker/attendance",
        params={"from": "2026-07-07", "to": "2026-07-07"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_attendance_is_staff_only(client, user_headers, admin_user, session_factory):
    await _enable_tracker(session_factory, admin_user.org_id)
    resp = await client.get("/api/v1/tracker/attendance", headers=user_headers)
    assert resp.status_code == 403
