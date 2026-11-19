"""Phase 3b · I1: DPDP readiness from SAVIO's own records: a score, a task list with evidence and
links, a map of where personal data is, and a named contact. Never a legal claim."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import AuditLog, GuardDiscovery
from tests.test_browser_policy import POLICY, _enroll, _guard_on


async def test_readiness_score_tasks_and_map(client, admin_headers, user_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)
    did, h = await _enroll(client, admin_headers, "ACCOUNTS-PC")

    r = (await client.get("/api/v1/guard/dpdp", headers=admin_headers)).json()
    items = {i["key"]: i for i in r["items"]}
    assert set(items) == {"data_map", "bitlocker", "defender", "firewall", "patch", "dlp", "usb", "accounts",
                          "cases", "contact", "records"}
    assert items["records"]["status"] == "done" and items["cases"]["status"] == "done"
    assert items["data_map"]["status"] == "todo" and "Turn on" in items["data_map"]["detail"]
    assert items["contact"]["status"] == "todo" and items["dlp"]["link"] == "/guard"
    assert r["score"] == round(100 * r["done"] / r["total"])
    assert "not legal advice" in r["disclaimer"]
    assert (await client.get("/api/v1/guard/dpdp", headers=user_headers)).status_code == 403

    # A weekly map, a name, company accounts, USB and the extension acting: those tasks are done.
    async with session_factory() as s:
        s.add(GuardDiscovery(device_id=uuid.UUID(did), org_id=admin_user.org_id, scanned_at=datetime.now(UTC),
                             files_scanned=900, files_skipped=0, truncated=False,
                             folders=[{"path": r"C:\Users\a\Documents\Clients", "files": 40, "files_with_findings": 12,
                                       "counts": {"Pan": 30}, "contact_lists": 2}]))
        await s.commit()
    await client.post("/api/v1/guard/browser-policy/end-pilot", headers=admin_headers)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={
        **POLICY, "discovery_enabled": True, "usb_mode": "read_only", "guard_mode": "warn",
        "chrome_extension_id": "abcdefghijklmnopabcdefghijklmnop"})
    for bad in ({"name": "a\u202eb", "email": "dpo@acme.in"}, {"name": "Asha", "email": "not an email"}, {"x": 1}):
        assert (await client.put("/api/v1/guard/dpdp/contact", headers=admin_headers, json=bad)).status_code == 422, bad
    assert (await client.put("/api/v1/guard/dpdp/contact", headers=admin_headers,
                             json={"name": " Asha Rao ", "email": "dpo@acme.in"})).status_code == 204
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [
        {"at": datetime.now(UTC).isoformat(), "windows_user": r"ACME\ravi", "site": "wetransfer.com", "channel": "file",
         "mode": "warn", "action": "warn", "counts": {"Pan": 5}, "contact_list": False, "keyword_hits": 0,
         "unknown": False}]})

    r2 = (await client.get("/api/v1/guard/dpdp", headers=admin_headers)).json()
    items = {i["key"]: i for i in r2["items"]}
    for key in ("data_map", "dlp", "usb", "accounts", "contact"):
        assert items[key]["status"] == "done", items[key]
    assert items["data_map"]["detail"].startswith("12 files with personal data on 1 PCs")
    assert r2["contact"] == {"name": "Asha Rao", "email": "dpo@acme.in"} and r2["score"] > r["score"]
    m = r2["map"]
    assert m["on_pcs"]["kinds"] == {"Pan": 30} and m["on_pcs"]["contact_lists"] == 2
    assert m["leaving"]["where"] == {"file_sharing": 1}
    async with session_factory() as s:
        assert (await s.execute(select(AuditLog).where(AuditLog.action == "dpdp.contact_update"))).scalars().one()
