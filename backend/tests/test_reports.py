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
    "installed_apps": [],
    "services": [],
    "windows_updates": [
        {"kb_article_id": "KB5012345", "title": "2026-07 Cumulative Update", "is_installed": False, "installed_on": None}
    ],
}


async def _enroll(client, admin_headers, hostname="RPT-PC", machine="rpt-machine"):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "rpt"}, headers=admin_headers
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": hostname,
            "machine_id": machine,
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return enroll.json()  # device_id, device_token


async def test_fleet_health_report(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enrolled['device_token']}"}
    push = await client.post("/api/v1/agent/telemetry", json=TELEMETRY_PAYLOAD, headers=device_headers)
    assert push.status_code == 200

    resp = await client.get("/api/v1/reports/fleet-health", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_devices"] == 1
    assert len(body["devices"]) == 1
    row = body["devices"][0]
    assert row["hostname"] == "RPT-PC"
    assert row["cpu_percent"] == 42.5
    assert row["critical_event_count"] == 1
    assert row["pending_update_count"] == 1
    assert body["total_critical_events"] == 1
    assert body["total_pending_updates"] == 1


async def test_fleet_health_export_is_csv(client, admin_headers):
    await _enroll(client, admin_headers)
    resp = await client.get("/api/v1/reports/fleet-health/export", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "hostname" in resp.text.splitlines()[0]
    assert "RPT-PC" in resp.text


async def test_remediation_report(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    device_id = enrolled["device_id"]
    await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "flush_dns", "reason": "site won't load"},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "office_repair", "reason": "office broken"},
        headers=admin_headers,
    )

    resp = await client.get("/api/v1/reports/remediation", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_tasks"] == 2
    assert body["by_tier"]["automatic"] == 1
    assert body["by_tier"]["approval_required"] == 1
    assert body["pending_approval"] == 1
    assert len(body["tasks"]) == 2
    assert body["tasks"][0]["device_hostname"] == "RPT-PC"


async def test_remediation_export_is_csv(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns issue"},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/reports/remediation/export", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "flush_dns" in resp.text


async def test_asset_report(client, admin_headers):
    await client.post(
        "/api/v1/assets",
        json={"name": "Dell Latitude", "category": "laptop", "status": "in_use", "purchase_cost": 1000.0},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/reports/assets", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["total"] == 1
    assert len(body["assets"]) == 1


async def test_asset_export_is_csv(client, admin_headers):
    await client.post(
        "/api/v1/assets",
        json={"name": "HP Monitor", "category": "monitor", "status": "in_storage"},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/reports/assets/export", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "HP Monitor" in resp.text


async def test_reports_require_auth(client):
    assert (await client.get("/api/v1/reports/fleet-health")).status_code == 401
    assert (await client.get("/api/v1/reports/remediation")).status_code == 401
    assert (await client.get("/api/v1/reports/assets")).status_code == 401


async def test_reports_are_org_scoped(client, admin_headers, other_org_user):
    await _enroll(client, admin_headers)
    other = await client.post(
        "/api/v1/auth/login",
        json={"email": other_org_user.email, "password": "UserPassw0rd!2345"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    resp = await client.get("/api/v1/reports/fleet-health", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json()["total_devices"] == 0
