"""Phase 3b · J3 Board report and J4 Compliance pack: printable pages from SAVIO's own records.
The board report is counts only (no person's name) for staff; the pack names staff and PCs and
is for admins. Data protection appears only with AI Guard. Neither claims a standard is met."""
from datetime import UTC, datetime, timedelta

from app.models import AuditLog, GuardCase, GuardIncident, UserRole
from tests.conftest import _create_user, auth_headers
from tests.test_brief import _enroll
from tests.test_browser_policy import _guard_on


async def test_board_report_counts_only_and_ai_guard_when_entitled(
        client, admin_headers, user_headers, session_factory, admin_user):
    await _enroll(client, admin_headers, "BOARD-1")
    await _enroll(client, admin_headers, "BOARD-2")
    tech = await _create_user(session_factory, admin_user.org_id, "tech@acme.com", "TechPassword123!",
                              UserRole.TECHNICIAN)
    tech_headers = await auth_headers(client, tech.email, "TechPassword123!")

    r = await client.get("/api/v1/reports/board", headers=tech_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["period_days"] == 30 and b["title"] == "Board report: month"
    assert b["kpis"]["devices"] == 2 and b["kpis"]["dpdp_score"] is None and b["kpis"]["breaches_found"] is None
    assert [s["key"] for s in b["sections"]][:2] == ["fleet", "security"]
    assert all({"title", "severity", "count", "advice"} <= set(x) for x in b["risks"]) and len(b["risks"]) <= 5
    assert (await client.get("/api/v1/reports/board", params={"days": 90}, headers=admin_headers)).json()[
        "title"] == "Board report: quarter"
    assert (await client.get("/api/v1/reports/board", params={"days": 7}, headers=admin_headers)).status_code == 422
    assert (await client.get("/api/v1/reports/board", headers=user_headers)).status_code == 403

    # With AI Guard: DPDP readiness and breach records, still with no one's name in it.
    await _guard_on(session_factory, admin_user.org_id)
    now = datetime.now(UTC)
    async with session_factory() as s:
        s.add_all([
            GuardCase(org_id=admin_user.org_id, windows_user=r"ACME\ravikumar", opened_at=now, last_event_at=now,
                      status="open", score=90, level="high", summary={}),
            GuardIncident(org_id=admin_user.org_id, title="Ravikumar's sheet", what_happened="", found_at=now,
                          kinds=[], status="open", steps={}, opened_at=now),
            GuardIncident(org_id=admin_user.org_id, title="Old one", what_happened="",
                          found_at=now - timedelta(days=60), kinds=[], status="closed", steps={}, opened_at=now),
        ])
        await s.commit()
    r = await client.get("/api/v1/reports/board", headers=admin_headers)
    k = r.json()["kpis"]
    assert isinstance(k["dpdp_score"], int) and k["breaches_found"] == 1 and k["breaches_open"] == 1
    assert "ravikumar" not in r.text.lower()
    assert any(s["key"] == "guard" for s in r.json()["sections"])


async def test_compliance_pack_evidence_admin_only(client, admin_headers, user_headers, session_factory, admin_user):
    await _enroll(client, admin_headers, "PACK-1")
    tech = await _create_user(session_factory, admin_user.org_id, "tech@acme.com", "TechPassword123!",
                              UserRole.TECHNICIAN)
    tech_headers = await auth_headers(client, tech.email, "TechPassword123!")
    async with session_factory() as s:
        s.add_all([AuditLog(org_id=admin_user.org_id, actor_id=None, action="policy.update", target_type="org"),
                   AuditLog(org_id=admin_user.org_id, actor_id=None, action="policy.update", target_type="org"),
                   AuditLog(org_id=admin_user.org_id, actor_id=None, action="user.create", target_type="user")])
        await s.commit()

    for h in (tech_headers, user_headers):
        assert (await client.get("/api/v1/reports/compliance-pack", headers=h)).status_code == 403
    p = (await client.get("/api/v1/reports/compliance-pack", headers=admin_headers)).json()
    assert p["period_days"] == 90 and "not a certificate" in p["disclaimer"]
    assert [d["hostname"] for d in p["security"]["per_device"]] == ["PACK-1"]
    assert p["access"]["by_role"] == {"admin": 1, "technician": 1, "user": 1}
    assert {s["role"] for s in p["access"]["staff"]} == {"admin", "technician"}
    by = {c["action"]: c["count"] for c in p["changes"]["by_action"]}
    assert by["policy.update"] == 2 and by["user.create"] == 1 and p["changes"]["total"] >= 3
    assert p["data_protection"] is None

    await _guard_on(session_factory, admin_user.org_id)
    async with session_factory() as s:
        s.add(GuardIncident(org_id=admin_user.org_id, title="KYC sheet", what_happened="", found_at=datetime.now(UTC),
                            kinds=["Pan"], status="open", steps={"contain": {"state": "done"}},
                            opened_at=datetime.now(UTC)))
        await s.commit()
    dp = (await client.get("/api/v1/reports/compliance-pack", params={"days": 30}, headers=admin_headers)).json()[
        "data_protection"]
    assert dp["total"] == 12 and len(dp["items"]) == 12
    assert dp["breaches"] == [{"title": "KYC sheet", "found_at": dp["breaches"][0]["found_at"], "status": "open",
                               "steps_settled": 1}]
