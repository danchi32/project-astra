"""Workforce Insights ("Tracker") — Phase 1 attendance.

Two layers: the pure span builder (no DB, so the time logic is pinned directly), and the
real path agent push → aggregation → portal read, including the entitlement gate that is the
whole point of a monitoring feature.
"""
from datetime import date, datetime, timezone

import pytest

from app.schemas.workforce import CategoryOverrides, WorkShiftWrite
from app.services.workforce import _productivity, _summarize, build_work_spans

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
    # Username is canonicalised to lower case on ingest so the Service's and Tray's
    # (case-insensitive) account names can't split one person into two rows.
    assert row["username"] == "acme\\rahul"
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
        params={"device_id": device_id, "username": "acme\\rahul", "day": "2026-07-07"},
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


# ── Productivity reclassification (category overrides) ─────────────────────────


def test_an_override_flips_the_bucket_but_keeps_active_total():
    # 4 foreground samples × 30s = 2 minutes in youtube.com (built-in: unproductive).
    groups = [("chrome", "youtube.com", "/watch", False, False, 4)]
    base = _productivity(groups, sample_seconds=30)
    assert (base.unproductive_minutes, base.productive_minutes) == (2, 0)

    flipped = _productivity(
        groups, sample_seconds=30, overrides={"domain": {"youtube.com": "productive"}})
    assert (flipped.productive_minutes, flipped.unproductive_minutes) == (2, 0)
    # An override only moves time between buckets; it never changes how much was active.
    assert flipped.active_minutes == base.active_minutes == 2


def test_category_overrides_normalise_keys_and_reject_bad_buckets():
    ov = CategoryOverrides(domain={"WWW.Reddit.com": "neutral"}, app={" Figma ": "productive"})
    assert ov.domain == {"reddit.com": "neutral"}   # www. dropped, lower-cased
    assert ov.app == {"figma": "productive"}         # trimmed, lower-cased
    with pytest.raises(ValueError):
        CategoryOverrides(domain={"x.com": "super"})  # not one of the three buckets


async def test_categories_round_trip_and_admin_only(
    client, admin_headers, user_headers, admin_user, session_factory
):
    await _enable_tracker(session_factory, admin_user.org_id)

    # Defaults: no overrides yet, but the buckets and the built-in catalogue are present.
    cfg = (await client.get("/api/v1/tracker/categories", headers=admin_headers)).json()
    assert cfg["buckets"] == ["productive", "neutral", "unproductive"]
    assert cfg["overrides"] == {"domain": {}, "app": {}}
    assert cfg["builtin"]["domain"]  # the shipped taxonomy is exposed for the UI

    # A non-admin staff member cannot rewrite the org's productivity rules.
    assert (await client.put(
        "/api/v1/tracker/categories", json={"domain": {"youtube.com": "productive"}},
        headers=user_headers)).status_code == 403

    # An invalid bucket is refused at the edge, not silently stored.
    assert (await client.put(
        "/api/v1/tracker/categories", json={"domain": {"x.com": "super"}},
        headers=admin_headers)).status_code == 422

    saved = await client.put(
        "/api/v1/tracker/categories",
        json={"domain": {"YouTube.com": "productive"}, "app": {"obs": "unproductive"}},
        headers=admin_headers)
    assert saved.status_code == 200
    assert saved.json()["overrides"] == {
        "domain": {"youtube.com": "productive"}, "app": {"obs": "unproductive"}}


async def test_an_override_reclassifies_collected_activity(
    client, admin_headers, admin_user, session_factory
):
    """The whole point: a saved rule changes how new activity is scored. Set youtube.com →
    productive, push a block of youtube foreground, and the person's productive time reflects it
    instead of the built-in unproductive default."""
    await _enable_tracker(session_factory, admin_user.org_id)
    assert (await client.put(
        "/api/v1/tracker/categories", json={"domain": {"youtube.com": "productive"}},
        headers=admin_headers)).status_code == 200

    device_token = await _enroll_device(client, admin_headers)
    youtube = [
        {"username": "ACME\\rahul", "kind": "foreground", "domain": "youtube.com",
         "path": "/watch", "occurred_at": f"2026-07-07T10:{m:02d}:00Z"}
        for m in range(0, 20)  # 20 samples
    ]
    assert (await _push(
        client, device_token, {**TELEMETRY_PAYLOAD, "activity": youtube})).status_code == 200

    detail = (await client.get(
        "/api/v1/tracker/user",
        params={"username": "acme\\rahul", "from": "2026-07-07", "to": "2026-07-07"},
        headers=admin_headers)).json()
    assert detail["productive_minutes"] > 0
    assert detail["unproductive_minutes"] == 0
    # And the app breakdown carries the overridden bucket, not the default. Match the host
    # component exactly (label is "youtube.com/watch") rather than a prefix/substring test, so
    # the assertion can't be satisfied by a look-alike like "youtube.com.evil.test".
    yt = next(a for a in detail["apps"] if a["label"].split("/", 1)[0] == "youtube.com")
    assert yt["bucket"] == "productive"


# ── Department shifts ─────────────────────────────────────────────────────────


def test_work_shift_validation():
    # A good shift normalises working_days (sorted, de-duped) and keeps the timezone.
    ok = WorkShiftWrite(
        name="India General", timezone="Asia/Kolkata",
        start_minute=540, end_minute=1050, working_days=[4, 0, 1, 2, 3, 0])
    assert ok.working_days == [0, 1, 2, 3, 4]

    with pytest.raises(ValueError):  # unknown timezone
        WorkShiftWrite(name="x", timezone="Mars/Olympus", start_minute=540, end_minute=1050)
    with pytest.raises(ValueError):  # weekday out of range
        WorkShiftWrite(name="x", timezone="UTC", start_minute=540, end_minute=1050,
                       working_days=[0, 7])
    with pytest.raises(ValueError):  # start == end
        WorkShiftWrite(name="x", timezone="UTC", start_minute=540, end_minute=540)
    with pytest.raises(ValueError):  # minute out of range
        WorkShiftWrite(name="x", timezone="UTC", start_minute=540, end_minute=1500)


async def _create_team(client, admin_headers, name):
    r = await client.post("/api/v1/grouping/teams", json={"name": name}, headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_shift_crud_and_team_assignment(
    client, admin_headers, user_headers, admin_user, session_factory
):
    await _enable_tracker(session_factory, admin_user.org_id)
    shift_body = {
        "name": "APAC", "timezone": "Asia/Kolkata",
        "start_minute": 330, "end_minute": 990, "working_days": [0, 1, 2, 3, 4],
    }

    # A non-admin staff member cannot define shifts.
    assert (await client.post(
        "/api/v1/tracker/shifts", json=shift_body, headers=user_headers)).status_code == 403

    created = await client.post("/api/v1/tracker/shifts", json=shift_body, headers=admin_headers)
    assert created.status_code == 201, created.text
    shift_id = created.json()["id"]
    assert created.json()["team_count"] == 0

    # Duplicate name is refused.
    assert (await client.post(
        "/api/v1/tracker/shifts", json=shift_body, headers=admin_headers)).status_code == 409

    # Assign the shift to a team, then read it back on the team-shifts list.
    team_id = await _create_team(client, admin_headers, "Support APAC")
    assigned = await client.put(
        f"/api/v1/tracker/teams/{team_id}/shift", json={"shift_id": shift_id}, headers=admin_headers)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["shift_name"] == "APAC"

    team_shifts = (await client.get("/api/v1/tracker/team-shifts", headers=admin_headers)).json()
    assert any(t["team_id"] == team_id and t["shift_id"] == shift_id for t in team_shifts)
    # The shift now reports one team assigned.
    shifts = (await client.get("/api/v1/tracker/shifts", headers=admin_headers)).json()
    assert next(s for s in shifts if s["id"] == shift_id)["team_count"] == 1

    # Deleting the shift un-assigns the team rather than deleting it.
    assert (await client.delete(
        f"/api/v1/tracker/shifts/{shift_id}", headers=admin_headers)).status_code == 204
    team_shifts = (await client.get("/api/v1/tracker/team-shifts", headers=admin_headers)).json()
    row = next(t for t in team_shifts if t["team_id"] == team_id)
    assert row["shift_id"] is None and row["shift_name"] is None


# ── Account → person, derived from device assignment ──────────────────────────


async def _device_id(client, admin_headers):
    return (await client.get("/api/v1/devices", headers=admin_headers)).json()[0]["id"]


async def _assign_device(session_factory, org_id, device_id, user_id):
    """The ordinary "give this laptop to X": an Asset linking the device to a person."""
    import uuid as _uuid

    from app.models.asset import Asset
    async with session_factory() as session:
        session.add(Asset(
            org_id=org_id, name="Work laptop",
            device_id=_uuid.UUID(str(device_id)), assigned_to_user_id=_uuid.UUID(str(user_id))))
        await session.commit()


async def test_device_assignment_resolves_the_person_on_attendance(
    client, admin_headers, admin_user, session_factory
):
    await _enable_tracker(session_factory, admin_user.org_id)
    device_token = await _enroll_device(client, admin_headers)
    device_id = await _device_id(client, admin_headers)

    # A person, and the device assigned to them — no Tracker-specific mapping step.
    user = (await client.post(
        "/api/v1/users",
        json={"email": "rahul.k@acme.com", "full_name": "Rahul K", "role": "user"},
        headers=admin_headers)).json()
    await _assign_device(session_factory, admin_user.org_id, device_id, user["id"])

    # Pushing attendance stamps that person onto the day straight from the assignment.
    await _push(client, device_token, {**TELEMETRY_PAYLOAD, "activity": ACTIVITY})

    rows = (await client.get(
        "/api/v1/tracker/attendance",
        params={"from": "2026-07-07", "to": "2026-07-07"}, headers=admin_headers)).json()
    assert rows[0]["user_id"] == user["id"]

    # The read-only accounts view reflects it (there is no assign endpoint any more).
    accounts = (await client.get("/api/v1/tracker/accounts", headers=admin_headers)).json()
    acc = next(a for a in accounts if a["username"] == "acme\\rahul")
    assert acc["user_id"] == user["id"] and acc["user_name"] == "Rahul K"


async def test_team_rollup_sums_attendance_by_team(
    client, admin_headers, admin_user, session_factory
):
    await _enable_tracker(session_factory, admin_user.org_id)
    device_token = await _enroll_device(client, admin_headers)
    device_id = await _device_id(client, admin_headers)

    # Assign the device to a person (so attendance resolves to them), then put them on a team.
    user = (await client.post(
        "/api/v1/users",
        json={"email": "rahul.t@acme.com", "full_name": "Rahul T", "role": "user"},
        headers=admin_headers)).json()
    await _assign_device(session_factory, admin_user.org_id, device_id, user["id"])
    await _push(client, device_token, {**TELEMETRY_PAYLOAD, "activity": ACTIVITY})  # 480m worked
    team = (await client.post(
        "/api/v1/grouping/teams", json={"name": "Night Owls"}, headers=admin_headers)).json()
    await client.put(
        f"/api/v1/grouping/teams/{team['id']}/users",
        json={"user_ids": [user["id"]]}, headers=admin_headers)

    rollup = (await client.get(
        "/api/v1/tracker/teams/rollup",
        params={"from": "2026-07-07", "to": "2026-07-07"}, headers=admin_headers)).json()
    row = next(t for t in rollup if t["team_id"] == team["id"])
    assert row["member_count"] == 1
    assert row["tracked_members"] == 1
    assert row["worked_minutes"] == 480     # the lock is excluded, same as attendance
    # No foreground in this push, so productivity is "not measured", not a zero.
    assert row["productive_minutes"] is None


# ── Attendance configuration ──────────────────────────────────────────────────


async def test_attendance_config_and_holidays(
    client, admin_headers, user_headers, admin_user, session_factory
):
    await _enable_tracker(session_factory, admin_user.org_id)

    # Defaults when nothing is configured: Mon–Fri, 8h / 4h, no holidays.
    cfg = (await client.get("/api/v1/tracker/attendance-config", headers=admin_headers)).json()
    assert cfg["working_days"] == [0, 1, 2, 3, 4]
    assert cfg["full_day_minutes"] == 480 and cfg["half_day_minutes"] == 240
    assert cfg["holidays"] == []

    # Writing settings is admin-only, and half-day cannot exceed full-day.
    assert (await client.put(
        "/api/v1/tracker/attendance-config",
        json={"working_days": [0, 1, 2, 3, 4, 5], "full_day_minutes": 480, "half_day_minutes": 240},
        headers=user_headers)).status_code == 403
    assert (await client.put(
        "/api/v1/tracker/attendance-config",
        json={"working_days": [0], "full_day_minutes": 300, "half_day_minutes": 400},
        headers=admin_headers)).status_code == 422

    saved = await client.put(
        "/api/v1/tracker/attendance-config",
        json={"working_days": [0, 1, 2, 3, 4, 5], "full_day_minutes": 540, "half_day_minutes": 270},
        headers=admin_headers)
    assert saved.status_code == 200
    assert saved.json()["working_days"] == [0, 1, 2, 3, 4, 5]
    assert saved.json()["full_day_minutes"] == 540

    # Holidays: add, reject a duplicate date, see it listed, then delete.
    h = await client.post(
        "/api/v1/tracker/holidays", json={"day": "2026-12-25", "name": "Christmas"},
        headers=admin_headers)
    assert h.status_code == 201, h.text
    assert (await client.post(
        "/api/v1/tracker/holidays", json={"day": "2026-12-25", "name": "Dup"},
        headers=admin_headers)).status_code == 409

    cfg = (await client.get("/api/v1/tracker/attendance-config", headers=admin_headers)).json()
    assert [(x["day"], x["name"]) for x in cfg["holidays"]] == [("2026-12-25", "Christmas")]

    assert (await client.delete(
        f"/api/v1/tracker/holidays/{h.json()['id']}", headers=admin_headers)).status_code == 204
    cfg = (await client.get("/api/v1/tracker/attendance-config", headers=admin_headers)).json()
    assert cfg["holidays"] == []
