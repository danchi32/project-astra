"""The agent auto-update relay endpoint: /api/v1/agent/update.

The backend must never be a signing authority — it only relays an already-signed manifest.
These tests lock two things: the endpoint is inert unless a channel is configured, and when a
channel is configured it passes the fetched manifest + signature through verbatim.
"""
from app.services import agent_update as agent_update_module
from tests.test_devices import create_enrollment_token, enroll_device


async def _device_token(client, admin_headers) -> str:
    token = await create_enrollment_token(client, admin_headers)
    body = await enroll_device(client, token["token"])
    return body["device_token"]


async def test_update_unauthenticated_is_rejected(client):
    response = await client.get("/api/v1/agent/update")
    assert response.status_code == 401


async def test_update_reports_nothing_when_channel_unconfigured(client, admin_headers):
    device_token = await _device_token(client, admin_headers)
    response = await client.get(
        "/api/v1/agent/update", headers={"Authorization": f"Bearer {device_token}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is False
    assert body["manifest"] is None
    assert body["signature"] is None


async def test_update_relays_signed_manifest_verbatim(client, admin_headers, monkeypatch):
    device_token = await _device_token(client, admin_headers)
    manifest = '{"version":"0.2.0","url":"https://example.com/a.zip","sha256":"ABC"}'
    signature = "c2lnbmF0dXJl"  # base64("signature")

    async def fake_current(self):
        return manifest, signature

    monkeypatch.setattr(
        agent_update_module.AgentUpdateService, "current", fake_current
    )

    response = await client.get(
        "/api/v1/agent/update", headers={"Authorization": f"Bearer {device_token}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    # Verbatim relay is essential — the agent verifies the signature over these exact bytes.
    assert body["manifest"] == manifest
    assert body["signature"] == signature


def _bare_settings(**extra):
    from app.core.config import Settings

    return Settings(
        jwt_secret_key="x", database_url="sqlite+aiosqlite:///:memory:", **extra
    )


def test_service_is_inert_without_both_urls():
    only_manifest = _bare_settings(agent_update_manifest_url="https://x/m.json")
    neither = _bare_settings()
    both = _bare_settings(
        agent_update_manifest_url="https://x/m.json",
        agent_update_signature_url="https://x/m.sig",
    )
    assert agent_update_module.AgentUpdateService(neither).configured is False
    assert agent_update_module.AgentUpdateService(only_manifest).configured is False
    assert agent_update_module.AgentUpdateService(both).configured is True


async def test_current_returns_none_when_unconfigured():
    assert await agent_update_module.AgentUpdateService(_bare_settings()).current() is None
