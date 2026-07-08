"""AI conversation tests. These run against the deterministic StubProvider
(no ASTRA_ANTHROPIC_API_KEY is set in the test env), so they are fully offline."""


async def _create_conversation(client, headers, title="Test chat"):
    resp = await client.post("/api/v1/conversations", json={"title": title}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _enroll_and_push_telemetry(client, admin_headers):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "ai-test"}, headers=admin_headers
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": "AI-PC-001",
            "machine_id": "ai-machine",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    device_token = enroll.json()["device_token"]
    await client.post(
        "/api/v1/agent/telemetry",
        json={
            "collected_at": "2026-07-08T10:00:00Z",
            "cpu_percent": 88.0,
            "ram_total_mb": 16384,
            "ram_used_mb": 15000,
            "disks": [{"drive": "C:", "total_gb": 500.0, "used_gb": 470.0, "free_gb": 30.0}],
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )


async def test_create_and_list_conversations(client, user_headers):
    cid = await _create_conversation(client, user_headers, title="My first chat")
    listing = await client.get("/api/v1/conversations", headers=user_headers)
    assert listing.status_code == 200
    assert any(c["id"] == cid and c["title"] == "My first chat" for c in listing.json())


async def test_conversations_require_auth(client):
    resp = await client.get("/api/v1/conversations")
    assert resp.status_code == 401


async def test_greeting_message_no_tools(client, user_headers):
    cid = await _create_conversation(client, user_headers)
    resp = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "hello there"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert "ASTRA" in body["assistant_message"]["content"]
    # A plain greeting gathers no evidence.
    assert not body["assistant_message"]["tool_trail"]


async def test_diagnostic_message_gathers_evidence(client, admin_headers):
    # Admin (a regular user works too) enrolls a device and asks a diagnostic question.
    await _enroll_and_push_telemetry(client, admin_headers)
    cid = await _create_conversation(client, admin_headers)
    resp = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "Is the CPU health okay on our devices?"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    trail = resp.json()["assistant_message"]["tool_trail"]
    assert trail, "expected the AI to gather evidence"
    assert trail[0]["tool"] == "list_devices"
    # The tool actually saw the enrolled device.
    assert "AI-PC-001" in trail[0]["output"]


async def test_messages_persisted_and_ordered(client, user_headers):
    cid = await _create_conversation(client, user_headers)
    await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "hello"},
        headers=user_headers,
    )
    msgs = await client.get(f"/api/v1/conversations/{cid}/messages", headers=user_headers)
    assert msgs.status_code == 200
    roles = [m["role"] for m in msgs.json()]
    assert roles == ["user", "assistant"]


async def test_cannot_access_other_users_conversation(client, admin_headers, user_headers):
    # A conversation created by the admin is not visible to a regular user.
    cid = await _create_conversation(client, admin_headers)
    resp = await client.get(f"/api/v1/conversations/{cid}/messages", headers=user_headers)
    assert resp.status_code == 404


async def test_send_to_unknown_conversation_is_404(client, user_headers):
    import uuid

    resp = await client.post(
        f"/api/v1/conversations/{uuid.uuid4()}/messages",
        json={"content": "hi"},
        headers=user_headers,
    )
    assert resp.status_code == 404


async def test_tool_dispatch_reads_telemetry_directly(session_factory, admin_user):
    # Unit-level: the telemetry tool returns real data for an enrolled device.
    from app.core.security import hash_opaque_token
    from app.models import Device
    from app.models.telemetry import TelemetrySnapshot
    from app.models.base import utcnow
    from app.services.ai.tools import dispatch_tool
    import json

    async with session_factory() as session:
        device = Device(
            org_id=admin_user.org_id,
            hostname="TOOL-PC",
            machine_id="tool-machine",
            os_version="Windows 11",
            agent_version="0.1.0",
            token_hash=hash_opaque_token("tool-device-token"),
        )
        session.add(device)
        await session.flush()
        session.add(
            TelemetrySnapshot(
                device_id=device.id,
                org_id=admin_user.org_id,
                cpu_percent=42.0,
                ram_total_mb=8192,
                ram_used_mb=4096,
                disks=[{"drive": "C:", "total_gb": 256, "used_gb": 100, "free_gb": 156}],
                collected_at=utcnow(),
            )
        )
        await session.commit()

        out = await dispatch_tool(
            session=session,
            org_id=admin_user.org_id,
            name="get_device_telemetry",
            tool_input={"hostname": "TOOL-PC"},
        )
    data = json.loads(out)
    assert data["cpu_percent"] == 42.0
    assert data["ram_percent"] == 50.0
