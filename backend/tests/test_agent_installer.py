"""The portal 'Install agent' flow: generate a pre-configured installer that mints
a working one-time enrollment token."""


async def test_generate_installer_returns_prefilled_script(client, admin_headers):
    resp = await client.post(
        "/api/v1/devices/agent-installer",
        json={"name": "Sales laptops", "server_url": "https://astra.example.com"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["filename"] == "Install-AstraAgent.ps1"
    assert body["server_url"] == "https://astra.example.com"
    # The script has the server URL and the exact token baked in.
    assert "https://astra.example.com" in body["script"]
    assert body["token"] in body["script"]
    assert "AstraAgent" in body["script"]


async def test_generated_token_can_enroll(client, admin_headers):
    resp = await client.post(
        "/api/v1/devices/agent-installer",
        json={"name": "Rollout"},
        headers=admin_headers,
    )
    token = resp.json()["token"]

    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": token,
            "hostname": "NEW-PC",
            "machine_id": "new-machine",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    assert enroll.status_code == 200, enroll.text
    assert "device_token" in enroll.json()


async def test_server_url_defaults_when_omitted(client, admin_headers):
    resp = await client.post(
        "/api/v1/devices/agent-installer",
        json={"name": "Default url"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    # Falls back to the server-configured public URL.
    assert resp.json()["server_url"] == "http://localhost:8000"


async def test_installer_requires_admin(client, user_headers):
    resp = await client.post(
        "/api/v1/devices/agent-installer",
        json={"name": "nope"},
        headers=user_headers,
    )
    assert resp.status_code == 403


async def test_installer_requires_auth(client):
    resp = await client.post("/api/v1/devices/agent-installer", json={"name": "nope"})
    assert resp.status_code == 401
