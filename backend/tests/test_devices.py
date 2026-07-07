import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import AuditLog, Device, EnrollmentToken
from app.models.base import utcnow

ENROLL_INFO = {
    "hostname": "LAPTOP-001",
    "machine_id": "machine-guid-001",
    "os_version": "Windows 11 Pro 23H2",
    "serial_number": "SN-12345",
    "agent_version": "0.1.0",
}


async def create_enrollment_token(client, admin_headers, **overrides) -> dict:
    body = {"name": "Office rollout", **overrides}
    response = await client.post(
        "/api/v1/devices/enrollment-tokens", json=body, headers=admin_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def enroll_device(client, enrollment_token: str, **overrides) -> dict:
    response = await client.post(
        "/api/v1/agent/enroll",
        json={"enrollment_token": enrollment_token, **ENROLL_INFO, **overrides},
    )
    assert response.status_code == 200, response.text
    return response.json()


# -- Enrollment tokens ----------------------------------------------------------


async def test_admin_creates_enrollment_token(client, admin_headers):
    body = await create_enrollment_token(client, admin_headers)
    assert body["token"]
    # The raw token is never shown again in the listing.
    listing = await client.get("/api/v1/devices/enrollment-tokens", headers=admin_headers)
    assert listing.status_code == 200
    assert "token" not in listing.json()[0]
    assert "token_hash" not in listing.json()[0]


async def test_regular_user_cannot_create_enrollment_token(client, user_headers):
    response = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "nope"}, headers=user_headers
    )
    assert response.status_code == 403


async def test_revoked_enrollment_token_rejected(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    revoke = await client.delete(
        f"/api/v1/devices/enrollment-tokens/{token['id']}", headers=admin_headers
    )
    assert revoke.status_code == 204
    response = await client.post(
        "/api/v1/agent/enroll", json={"enrollment_token": token["token"], **ENROLL_INFO}
    )
    assert response.status_code == 401


async def test_expired_enrollment_token_rejected(client, admin_headers, org, session_factory):
    raw = "expired-token-raw-value"
    async with session_factory() as session:
        session.add(
            EnrollmentToken(
                org_id=org.id,
                name="expired",
                token_hash=hash_opaque_token(raw),
                expires_at=utcnow() - timedelta(days=1),
            )
        )
        await session.commit()
    response = await client.post(
        "/api/v1/agent/enroll", json={"enrollment_token": raw, **ENROLL_INFO}
    )
    assert response.status_code == 401


async def test_garbage_enrollment_token_rejected(client):
    response = await client.post(
        "/api/v1/agent/enroll", json={"enrollment_token": "not-a-token", **ENROLL_INFO}
    )
    assert response.status_code == 401


# -- Enrollment -----------------------------------------------------------------


async def test_enroll_creates_device_and_audit_entry(client, admin_headers, session_factory):
    token = await create_enrollment_token(client, admin_headers)
    body = await enroll_device(client, token["token"])
    assert body["device_id"]
    assert body["device_token"]
    async with session_factory() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.action == "device.enroll"))
        entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].actor_id is None
    assert entries[0].detail["hostname"] == "LAPTOP-001"


async def test_reenroll_same_machine_rotates_token(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    first = await enroll_device(client, token["token"])
    second = await enroll_device(client, token["token"], hostname="LAPTOP-001-REIMAGED")

    assert second["device_id"] == first["device_id"]
    assert second["device_token"] != first["device_token"]

    # The old credential must stop working.
    old = await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.1.0"},
        headers={"Authorization": f"Bearer {first['device_token']}"},
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.1.0"},
        headers={"Authorization": f"Bearer {second['device_token']}"},
    )
    assert new.status_code == 200


async def test_decommissioned_device_cannot_reenroll(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    enrolled = await enroll_device(client, token["token"])
    patch = await client.patch(
        f"/api/v1/devices/{enrolled['device_id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert patch.status_code == 200
    response = await client.post(
        "/api/v1/agent/enroll", json={"enrollment_token": token["token"], **ENROLL_INFO}
    )
    assert response.status_code == 401


# -- Heartbeat ------------------------------------------------------------------


async def test_heartbeat_marks_device_online(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    enrolled = await enroll_device(client, token["token"])

    before = await client.get(f"/api/v1/devices/{enrolled['device_id']}", headers=admin_headers)
    assert before.json()["status"] == "offline"

    beat = await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.2.0", "logged_in_user": "ACME\\jdoe"},
        headers={"Authorization": f"Bearer {enrolled['device_token']}"},
    )
    assert beat.status_code == 200

    after = await client.get(f"/api/v1/devices/{enrolled['device_id']}", headers=admin_headers)
    body = after.json()
    assert body["status"] == "online"
    assert body["agent_version"] == "0.2.0"
    assert body["logged_in_user"] == "ACME\\jdoe"
    assert body["last_seen_at"] is not None


async def test_heartbeat_with_invalid_token_rejected(client):
    response = await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.1.0"},
        headers={"Authorization": "Bearer forged-device-token"},
    )
    assert response.status_code == 401


async def test_deactivated_device_heartbeat_rejected(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    enrolled = await enroll_device(client, token["token"])
    await client.patch(
        f"/api/v1/devices/{enrolled['device_id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.1.0"},
        headers={"Authorization": f"Bearer {enrolled['device_token']}"},
    )
    assert response.status_code == 401


async def test_device_token_cannot_call_portal_apis(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    enrolled = await enroll_device(client, token["token"])
    response = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {enrolled['device_token']}"}
    )
    assert response.status_code == 401


# -- Portal device management ----------------------------------------------------


async def test_device_list_is_org_scoped(client, admin_headers, other_org, session_factory):
    token = await create_enrollment_token(client, admin_headers)
    await enroll_device(client, token["token"])
    async with session_factory() as session:
        session.add(
            Device(
                org_id=other_org.id,
                hostname="GLOBEX-PC",
                machine_id="globex-machine",
                os_version="Windows 11",
                agent_version="0.1.0",
                token_hash=hash_opaque_token("other-org-device-token"),
            )
        )
        await session.commit()

    response = await client.get("/api/v1/devices", headers=admin_headers)
    assert response.status_code == 200
    hostnames = {d["hostname"] for d in response.json()}
    assert hostnames == {"LAPTOP-001"}


async def test_regular_user_cannot_list_devices(client, user_headers):
    response = await client.get("/api/v1/devices", headers=user_headers)
    assert response.status_code == 403


async def test_device_from_other_org_is_404(client, admin_headers, other_org, session_factory):
    async with session_factory() as session:
        device = Device(
            org_id=other_org.id,
            hostname="GLOBEX-PC",
            machine_id="globex-machine",
            os_version="Windows 11",
            agent_version="0.1.0",
            token_hash=hash_opaque_token("other-org-device-token-2"),
        )
        session.add(device)
        await session.commit()
        device_id = device.id
    response = await client.get(f"/api/v1/devices/{device_id}", headers=admin_headers)
    assert response.status_code == 404


async def test_admin_deletes_device(client, admin_headers):
    token = await create_enrollment_token(client, admin_headers)
    enrolled = await enroll_device(client, token["token"])
    response = await client.delete(
        f"/api/v1/devices/{enrolled['device_id']}", headers=admin_headers
    )
    assert response.status_code == 204
    gone = await client.get(f"/api/v1/devices/{enrolled['device_id']}", headers=admin_headers)
    assert gone.status_code == 404


async def test_unknown_device_is_404(client, admin_headers):
    response = await client.get(f"/api/v1/devices/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404
