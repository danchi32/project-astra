"""Phase 3 · D5: each PC's map of where sensitive files are, folder counts only, replaced by
each scan, read by admins only, and switched on per org in the AI Guard policy."""
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import GuardDiscovery
from tests.test_browser_policy import POLICY, _enroll, _guard_on


def _map(**over):
    m = {"scanned_at": datetime.now(UTC).isoformat(), "files_scanned": 120, "files_skipped": 2, "truncated": False,
         "folders": [{"path": r"C:\Users\asha\Documents\Clients", "files": 14, "files_with_findings": 9,
                      "counts": {"Pan": 30, "IndianMobile": 41, "Email": 0}, "contact_lists": 2},
                     {"path": r"C:\Users\asha\Downloads", "files": 40, "files_with_findings": 1,
                      "counts": {"Aadhaar": 1}, "contact_lists": 0}]}
    return {**m, **over}


async def test_the_switch_and_the_map(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "discovery_enabled": True})
    _, h = await _enroll(client, admin_headers, "ACCOUNTS-PC")
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["discovery_enabled"] is True
    assert r.json()["policy"]["discovery_enabled"] is True

    assert (await client.post("/api/v1/agent/guard/discovery", headers=h, json=_map())).status_code == 204
    d = (await client.get("/api/v1/guard/discovery", headers=admin_headers)).json()
    assert (d["pcs"], d["files_with_findings"], d["contact_lists"]) == (1, 10, 2)
    assert d["kinds"] == {"IndianMobile": 41, "Pan": 30, "Aadhaar": 1}
    pc = d["devices"][0]
    assert pc["hostname"] == "ACCOUNTS-PC" and pc["folders"][0]["path"].endswith("Clients")
    assert "Email" not in pc["folders"][0]["counts"]                        # zero counts dropped

    # The next scan replaces the map rather than adding to it.
    await client.post("/api/v1/agent/guard/discovery", headers=h, json=_map(folders=[]))
    assert (await client.get("/api/v1/guard/discovery", headers=admin_headers)).json()["files_with_findings"] == 0


async def test_the_schema_is_fixed(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers)
    folder = _map()["folders"][0]
    for bad in (_map(folders=[{**folder, "files_names": ["kyc.csv"]}]),       # no file names, under any name
                _map(folders=[{**folder, "counts": {"Passwords": 1}}]),
                _map(folders=[{**folder, "path": "a\nb"}]),
                _map(folders=[{**folder, "path": "x" * 401}]),
                _map(folders=[folder] * 501),
                _map(folders=[{**folder, "old": 10}]),                         # I1: more old than found
                _map(folders=[{**folder, "old": -1}]),
                {**_map(), "sample": "ABCPE1234F"}):
        assert (await client.post("/api/v1/agent/guard/discovery", headers=h, json=bad)).status_code == 422
    # I1: the old-file count is kept when sent, and absent (not counted) when an older agent sends none.
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "discovery_enabled": True})
    other = _map()["folders"][1]
    assert (await client.post("/api/v1/agent/guard/discovery", headers=h,
                              json=_map(folders=[{**folder, "old": 3}, other]))).status_code == 204
    got = (await client.get("/api/v1/guard/discovery", headers=admin_headers)).json()["devices"][0]["folders"]
    assert [f["old"] for f in got] == [3, None]


async def test_without_the_add_on_and_roles(client, admin_headers, session_factory, admin_user, org):
    from app.models import UserRole
    from tests.conftest import _create_user, auth_headers

    _, h = await _enroll(client, admin_headers)
    assert (await client.post("/api/v1/agent/guard/discovery", headers=h, json=_map())).status_code == 204
    async with session_factory() as s:
        assert (await s.execute(select(GuardDiscovery))).scalars().first() is None
    await _guard_on(session_factory, admin_user.org_id)
    await _create_user(session_factory, org.id, "tech@acme.com", "TechPassw0rd!2345", UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", "TechPassw0rd!2345")
    assert (await client.get("/api/v1/guard/discovery", headers=tech)).status_code == 403
