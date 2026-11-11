"""B1 — repairs the agent made while offline land in the audit log when it reconnects."""
from sqlalchemy import select

from app.models import AuditLog


async def _device(client, admin_headers):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "WIFI-PC", "machine_id": "wifi-1",
        "os_version": "Windows 11", "agent_version": "0.14.0"})
    return {"Authorization": f"Bearer {r.json()['device_token']}"}


async def test_offline_repairs_are_audited(client, admin_headers, session_factory):
    dev = await _device(client, admin_headers)
    r = await client.post("/api/v1/agent/offline-events", headers=dev, json={"events": [
        {"at": "2026-11-11T09:00:00Z", "diagnosis": "DnsFailing", "step": "FlushDns",
         "step_ok": True, "output": "Successfully flushed", "fixed_after": False},
        {"at": "2026-11-11T09:00:10Z", "trigger": "tray", "diagnosis": "DnsFailing",
         "step": "RenewIp", "step_ok": True, "fixed_after": True},
    ]})
    assert r.status_code == 204, r.text
    async with session_factory() as s:
        rows = (await s.execute(select(AuditLog).where(AuditLog.action == "device.offline_self_heal")
                                .order_by(AuditLog.created_at))).scalars().all()
    assert [(e.detail["step"], e.detail["fixed_after"]) for e in rows] == [("FlushDns", False), ("RenewIp", True)]
    assert rows[1].detail["trigger"] == "tray" and rows[0].detail["hostname"] == "WIFI-PC"


async def test_needs_a_device_token_and_bounded_input(client, admin_headers):
    assert (await client.post("/api/v1/agent/offline-events", json={"events": []})).status_code == 401
    dev = await _device(client, admin_headers)
    too_many = {"events": [{"at": "2026-11-11T09:00:00Z", "diagnosis": "NoAddress"}] * 201}
    assert (await client.post("/api/v1/agent/offline-events", headers=dev, json=too_many)).status_code == 422
