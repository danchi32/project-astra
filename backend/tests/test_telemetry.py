from datetime import datetime, timezone

TELEMETRY_PAYLOAD = {
    "collected_at": "2026-07-07T10:00:00Z",
    "cpu_percent": 42.5,
    "ram_total_mb": 16384,
    "ram_used_mb": 8192,
    "disks": [{"drive": "C:", "total_gb": 500.0, "used_gb": 200.0, "free_gb": 300.0}],
    "event_logs": [
        {
            "log_name": "System",
            "source": "Service Control Manager",
            "event_id": 7034,
            "level": "Error",
            "message": "The Print Spooler service terminated unexpectedly.",
            "occurred_at": "2026-07-07T09:55:00Z",
        }
    ],
    "installed_apps": [
        {"name": "Microsoft Office", "version": "16.0", "publisher": "Microsoft", "install_date": "20240101"}
    ],
    "services": [
        {"name": "Spooler", "display_name": "Print Spooler", "status": "Stopped", "start_type": "Automatic"}
    ],
    "windows_updates": [
        {"kb_article_id": "KB5012345", "title": "2026-07 Cumulative Update", "is_installed": False, "installed_on": None}
    ],
}


async def _enroll_device(client, admin_headers):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens",
        json={"name": "telemetry-test"},
        headers=admin_headers,
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": "TEL-PC-001",
            "machine_id": "tel-machine",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return enroll.json()["device_token"]


async def test_agent_pushes_telemetry(client, admin_headers):
    device_token = await _enroll_device(client, admin_headers)
    headers = {"Authorization": f"Bearer {device_token}"}
    response = await client.post("/api/v1/agent/telemetry", json=TELEMETRY_PAYLOAD, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


async def test_telemetry_requires_device_token(client, admin_headers):
    response = await client.post(
        "/api/v1/agent/telemetry", json=TELEMETRY_PAYLOAD, headers=admin_headers
    )
    assert response.status_code == 401


async def test_snapshots_visible_in_portal(client, admin_headers):
    device_token = await _enroll_device(client, admin_headers)
    await client.post(
        "/api/v1/agent/telemetry",
        json=TELEMETRY_PAYLOAD,
        headers={"Authorization": f"Bearer {device_token}"},
    )

    devices = await client.get("/api/v1/devices", headers=admin_headers)
    device_id = devices.json()[0]["id"]

    snaps = await client.get(f"/api/v1/devices/{device_id}/telemetry", headers=admin_headers)
    assert snaps.status_code == 200
    assert len(snaps.json()) == 1
    snap = snaps.json()[0]
    assert snap["cpu_percent"] == 42.5
    assert snap["ram_used_mb"] == 8192
    assert snap["disks"][0]["drive"] == "C:"


async def test_event_logs_visible_in_portal(client, admin_headers):
    device_token = await _enroll_device(client, admin_headers)
    await client.post(
        "/api/v1/agent/telemetry",
        json=TELEMETRY_PAYLOAD,
        headers={"Authorization": f"Bearer {device_token}"},
    )
    devices = await client.get("/api/v1/devices", headers=admin_headers)
    device_id = devices.json()[0]["id"]

    logs = await client.get(f"/api/v1/devices/{device_id}/events", headers=admin_headers)
    assert logs.status_code == 200
    assert len(logs.json()) == 1
    assert logs.json()[0]["level"] == "Error"
    assert logs.json()[0]["event_id"] == 7034


async def test_apps_services_updates_visible(client, admin_headers):
    device_token = await _enroll_device(client, admin_headers)
    await client.post(
        "/api/v1/agent/telemetry",
        json=TELEMETRY_PAYLOAD,
        headers={"Authorization": f"Bearer {device_token}"},
    )
    devices = await client.get("/api/v1/devices", headers=admin_headers)
    device_id = devices.json()[0]["id"]

    apps = await client.get(f"/api/v1/devices/{device_id}/apps", headers=admin_headers)
    assert apps.status_code == 200
    assert apps.json()[0]["name"] == "Microsoft Office"

    services = await client.get(f"/api/v1/devices/{device_id}/services", headers=admin_headers)
    assert services.json()[0]["status"] == "Stopped"

    updates = await client.get(f"/api/v1/devices/{device_id}/updates", headers=admin_headers)
    assert updates.json()[0]["kb_article_id"] == "KB5012345"
    assert updates.json()[0]["is_installed"] is False


async def test_dashboard_summary_reflects_telemetry(client, admin_headers):
    device_token = await _enroll_device(client, admin_headers)
    beat = await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.1.0"},
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert beat.status_code == 200

    await client.post(
        "/api/v1/agent/telemetry",
        json=TELEMETRY_PAYLOAD,
        headers={"Authorization": f"Bearer {device_token}"},
    )

    summary = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_devices"] == 1
    assert body["online_devices"] == 1
    assert body["avg_cpu_percent"] == 42.5
    assert body["critical_event_count"] == 1
    assert body["pending_update_count"] == 1


async def test_regular_user_cannot_read_telemetry(client, user_headers, admin_headers):
    device_token = await _enroll_device(client, admin_headers)
    devices = await client.get("/api/v1/devices", headers=admin_headers)
    device_id = devices.json()[0]["id"]
    response = await client.get(f"/api/v1/devices/{device_id}/telemetry", headers=user_headers)
    assert response.status_code == 403


async def test_telemetry_org_isolation(client, admin_headers, other_org_user, user_headers):
    # other_org_user tries to access a device from the main org
    device_token = await _enroll_device(client, admin_headers)
    devices = await client.get("/api/v1/devices", headers=admin_headers)
    device_id = devices.json()[0]["id"]

    other_token_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": other_org_user.email, "password": "UserPassw0rd!2345"},
    )
    other_headers = {"Authorization": f"Bearer {other_token_resp.json()['access_token']}"}
    response = await client.get(f"/api/v1/devices/{device_id}/telemetry", headers=other_headers)
    assert response.status_code in (403, 404)
