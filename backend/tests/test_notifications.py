async def _enroll(client, admin_headers, hostname="NTF-PC", machine="ntf-machine"):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "ntf"}, headers=admin_headers
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


async def test_pending_approval_creates_notification(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "office_repair", "reason": "office broken"},
        headers=admin_headers,
    )
    assert resp.status_code == 201

    notes = await client.get("/api/v1/notifications", headers=admin_headers)
    assert notes.status_code == 200
    body = notes.json()
    assert len(body) == 1
    assert body[0]["category"] == "remediation"
    assert body[0]["severity"] == "warning"
    assert body[0]["title"] == "Approval needed"
    assert "NTF-PC" in body[0]["message"]
    assert body[0]["is_read"] is False


async def test_automatic_action_does_not_notify(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns issue"},
        headers=admin_headers,
    )
    assert resp.status_code == 201

    notes = await client.get("/api/v1/notifications", headers=admin_headers)
    assert notes.json() == []


async def test_failed_remediation_creates_notification(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enrolled['device_token']}"}
    created = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns issue"},
        headers=admin_headers,
    )
    task_id = created.json()["id"]

    claimed = await client.get("/api/v1/agent/tasks", headers=device_headers)
    assert claimed.status_code == 200

    result = await client.post(
        f"/api/v1/agent/tasks/{task_id}/result",
        json={"success": False, "output": "dns flush failed"},
        headers=device_headers,
    )
    assert result.status_code == 204

    notes = await client.get("/api/v1/notifications", headers=admin_headers)
    body = notes.json()
    assert len(body) == 1
    assert body[0]["severity"] == "critical"
    assert body[0]["title"] == "Remediation failed"


async def test_unread_count_and_mark_read(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "office_repair", "reason": "x"},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "registry_fix",
              "reason": "y", "params": {"fix_id": "abc"}},
        headers=admin_headers,
    )

    unread = await client.get("/api/v1/notifications/unread-count", headers=admin_headers)
    assert unread.json()["unread_count"] == 2

    notes = (await client.get("/api/v1/notifications", headers=admin_headers)).json()
    first_id = notes[0]["id"]
    marked = await client.post(f"/api/v1/notifications/{first_id}/read", headers=admin_headers)
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True

    unread_after = await client.get("/api/v1/notifications/unread-count", headers=admin_headers)
    assert unread_after.json()["unread_count"] == 1

    unread_only = await client.get(
        "/api/v1/notifications", params={"unread_only": True}, headers=admin_headers
    )
    assert len(unread_only.json()) == 1


async def test_mark_all_read(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    for action in ("office_repair", "network_reset"):
        await client.post(
            "/api/v1/remediations",
            json={"device_id": enrolled["device_id"], "action_id": action, "reason": "x"},
            headers=admin_headers,
        )
    resp = await client.post("/api/v1/notifications/read-all", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["marked"] == 2
    unread = await client.get("/api/v1/notifications/unread-count", headers=admin_headers)
    assert unread.json()["unread_count"] == 0


async def test_notifications_require_auth(client):
    assert (await client.get("/api/v1/notifications")).status_code == 401
    assert (await client.get("/api/v1/notifications/unread-count")).status_code == 401
    assert (await client.post("/api/v1/notifications/read-all")).status_code == 401


async def test_notifications_are_org_scoped(client, admin_headers, other_org_user):
    enrolled = await _enroll(client, admin_headers)
    await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "office_repair", "reason": "x"},
        headers=admin_headers,
    )
    other = await client.post(
        "/api/v1/auth/login",
        json={"email": other_org_user.email, "password": "UserPassw0rd!2345"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    resp = await client.get("/api/v1/notifications", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json() == []
