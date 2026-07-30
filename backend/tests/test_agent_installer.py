"""The portal 'Install agent' flow: the org's ready-to-run installer carries the
permanent per-org enrollment key (no token step, no expiry)."""


async def test_installer_returns_enrollment_details(client, admin_headers):
    resp = await client.get("/api/v1/devices/installer", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["filename"] == "Install-AstraAgent.ps1"
    # Falls back to the server-configured public URL (no per-request override).
    assert body["server_url"] == "http://localhost:8000"
    assert body["enrollment_key"]
    # The runnable artefact is the portable bundle; this endpoint no longer returns a
    # script (the online self-download installer was removed).
    assert "script" not in body


async def test_installer_key_can_enroll(client, admin_headers):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": key,
            "hostname": "NEW-PC",
            "machine_id": "new-machine",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    assert enroll.status_code == 200, enroll.text
    assert "device_token" in enroll.json()


async def test_installer_requires_admin(client, user_headers):
    assert (await client.get("/api/v1/devices/installer", headers=user_headers)).status_code == 403


async def test_installer_requires_auth(client):
    assert (await client.get("/api/v1/devices/installer")).status_code == 401
