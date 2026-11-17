"""BitLocker recovery key escrow (2a+): stored encrypted, listed without the password, revealed
only by an org admin, and every reveal audited."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import crypto
from app.core.config import get_settings
from app.models import AuditLog, DeviceBitLockerKey, Organization, User, UserRole
from app.models.base import utcnow
from tests.conftest import ADMIN_PASSWORD, _create_user, auth_headers

PASSWORD = "123456-234567-345678-456789-567890-678901-789012-890123"
KEY = {"drive": "C:", "protector_id": "{1A2B3C4D-1111-2222-3333-444455556666}", "recovery_password": PASSWORD}


@pytest.fixture(autouse=True)
def _secrets_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)


async def _enroll(client, headers, machine="bl-1"):
    key = (await client.get("/api/v1/devices/installer", headers=headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "BL-PC", "machine_id": machine,
        "os_version": "Windows 11", "agent_version": "0.15.0"})
    body = r.json()
    return body["device_token"], body["device_id"]


async def _escrow(client, token, keys):
    return await client.post("/api/v1/agent/bitlocker-keys", json={"keys": keys},
                             headers={"Authorization": f"Bearer {token}"})


async def test_escrow_is_encrypted_and_listed_without_the_password(client, admin_headers, session_factory):
    token, device_id = await _enroll(client, admin_headers)
    r = await _escrow(client, token, [KEY])
    assert r.status_code == 204, r.text

    async with session_factory() as s:
        row = (await s.execute(select(DeviceBitLockerKey))).scalar_one()
        assert row.recovery_password_enc != PASSWORD and PASSWORD not in row.recovery_password_enc
        assert crypto.decrypt(row.recovery_password_enc) == PASSWORD
        assert row.protector_id == "1a2b3c4d-1111-2222-3333-444455556666"   # one stored form
        escrow = (await s.execute(select(AuditLog).where(
            AuditLog.action == "device.bitlocker_key_escrow"))).scalar_one()
        assert PASSWORD not in str(escrow.detail)

    listed = (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=admin_headers)).json()
    assert len(listed) == 1 and listed[0]["drive"] == "C:"
    assert "recovery_password" not in listed[0]


async def test_the_same_key_twice_is_stored_once(client, admin_headers, session_factory):
    token, _ = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    await _escrow(client, token, [dict(KEY, protector_id=KEY["protector_id"].lower().strip("{}"))])
    async with session_factory() as s:
        assert len((await s.execute(select(DeviceBitLockerKey))).scalars().all()) == 1


async def test_reveal_is_admin_only_and_audited(client, admin_headers, admin_user, user_headers, session_factory):
    token, device_id = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    key_id = (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=admin_headers)).json()[0]["id"]
    url = f"/api/v1/devices/{device_id}/bitlocker-keys/{key_id}/reveal"

    await _create_user(session_factory, admin_user.org_id, "tech@acme.com", ADMIN_PASSWORD, UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", ADMIN_PASSWORD)
    assert (await client.post(url, headers=tech)).status_code == 403
    assert (await client.post(url, headers=user_headers)).status_code == 403
    assert (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=tech)).status_code == 403

    r = await client.post(url, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["recovery_password"] == PASSWORD

    async with session_factory() as s:
        reveal = (await s.execute(select(AuditLog).where(
            AuditLog.action == "device.bitlocker_key_reveal"))).scalar_one()
        assert reveal.actor_id == admin_user.id
        assert reveal.detail["by"] == admin_user.email and reveal.detail["drive"] == "C:"
        assert PASSWORD not in str(reveal.detail)


async def test_another_org_cannot_list_or_reveal(client, admin_headers, other_org, session_factory):
    token, device_id = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    key_id = (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=admin_headers)).json()[0]["id"]

    await _create_user(session_factory, other_org.id, "admin@globex.com", ADMIN_PASSWORD, UserRole.ADMIN)
    other = await auth_headers(client, "admin@globex.com", ADMIN_PASSWORD)
    assert (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=other)).status_code == 404
    r = await client.post(f"/api/v1/devices/{device_id}/bitlocker-keys/{key_id}/reveal", headers=other)
    assert r.status_code == 404


@pytest.mark.parametrize("bad", [
    dict(KEY, recovery_password="12345a-234567-345678-456789-567890-678901-789012-890123"),  # not digits
    dict(KEY, drive="1:"),
    dict(KEY, protector_id="{not-a-guid-not-a-guid-not-a-guid-xxxxxx}"),
])
async def test_malformed_keys_are_refused_and_nothing_is_stored(client, admin_headers, session_factory, bad):
    token, _ = await _enroll(client, admin_headers)
    r = await _escrow(client, token, [bad])
    assert r.status_code in (400, 422), r.text
    async with session_factory() as s:
        assert (await s.execute(select(DeviceBitLockerKey))).scalars().all() == []


async def test_without_an_encryption_key_the_server_refuses_and_writes_nothing(
        client, admin_headers, session_factory, monkeypatch):
    token, _ = await _enroll(client, admin_headers)
    monkeypatch.setattr(get_settings(), "secrets_key", None, raising=False)
    r = await _escrow(client, token, [KEY])
    assert r.status_code == 503
    async with session_factory() as s:
        assert (await s.execute(select(DeviceBitLockerKey))).scalars().all() == []


async def test_a_view_as_session_cannot_reveal(client, admin_user, admin_headers, other_org, session_factory):
    await _create_user(session_factory, other_org.id, "admin@globex.com", ADMIN_PASSWORD, UserRole.ADMIN)
    customer = await auth_headers(client, "admin@globex.com", ADMIN_PASSWORD)
    token, device_id = await _enroll(client, customer, machine="bl-globex")
    await _escrow(client, token, [KEY])
    key_id = (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=customer)).json()[0]["id"]

    async with session_factory() as s:
        (await s.get(User, admin_user.id)).is_platform_admin = True
        (await s.get(Organization, other_org.id)).support_access_until = utcnow() + timedelta(hours=1)
        await s.commit()
    vt = await client.post(f"/api/v1/platform/organizations/{other_org.id}/view-token", headers=admin_headers)
    view = {"Authorization": f"Bearer {vt.json()['access_token']}"}
    r = await client.post(f"/api/v1/devices/{device_id}/bitlocker-keys/{key_id}/reveal", headers=view)
    assert r.status_code == 403


# ── security review fixes ──────────────────────────────────────────────────────────


async def test_a_replaced_platform_key_is_healed_by_the_next_report(
        client, admin_headers, session_factory, monkeypatch):
    token, device_id = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    new_key = crypto.generate_key()
    monkeypatch.setattr(get_settings(), "secrets_key", new_key, raising=False)
    # The stored copy no longer decrypts; the next report re-escrows it under the new key.
    assert (await _escrow(client, token, [KEY])).status_code == 204
    async with session_factory() as s:
        row = (await s.execute(select(DeviceBitLockerKey))).scalar_one()
        assert crypto.decrypt(row.recovery_password_enc) == PASSWORD
        assert (await s.execute(select(AuditLog).where(
            AuditLog.action == "device.bitlocker_key_re_escrow"))).scalar_one() is not None


async def test_a_different_password_for_a_known_key_is_kept_out_and_audited(
        client, admin_headers, session_factory):
    token, _ = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    other = "999999-234567-345678-456789-567890-678901-789012-890123"
    assert (await _escrow(client, token, [dict(KEY, recovery_password=other)])).status_code == 204
    async with session_factory() as s:
        row = (await s.execute(select(DeviceBitLockerKey))).scalar_one()
        assert crypto.decrypt(row.recovery_password_enc) == PASSWORD          # first copy kept
        conflict = (await s.execute(select(AuditLog).where(
            AuditLog.action == "device.bitlocker_key_conflict"))).scalar_one()
        assert other not in str(conflict.detail) and PASSWORD not in str(conflict.detail)


async def test_a_device_cannot_escrow_more_than_the_cap(client, admin_headers, session_factory):
    from app.services.bitlocker_keys import MAX_KEYS_PER_DEVICE
    token, device_id = await _enroll(client, admin_headers)
    async with session_factory() as s:
        from app.models import Device
        dev = await s.get(Device, device_id)
        for i in range(MAX_KEYS_PER_DEVICE):
            s.add(DeviceBitLockerKey(device_id=dev.id, org_id=dev.org_id, drive="D:",
                                     protector_id=f"00000000-0000-0000-0000-{i:012d}",
                                     recovery_password_enc="x", escrowed_at=utcnow()))
        await s.commit()
    assert (await _escrow(client, token, [KEY])).status_code == 409


async def test_an_error_never_echoes_a_password(client, admin_headers):
    token, _ = await _enroll(client, admin_headers)
    bad = "12345a-234567-345678-456789-567890-678901-789012-890123"
    r = await _escrow(client, token, [dict(KEY, recovery_password=bad)])
    assert r.status_code in (400, 422) and bad not in r.text
    r = await _escrow(client, token, [KEY] * 11)                    # too many in one report
    assert r.status_code in (400, 422) and PASSWORD not in r.text


async def test_reveal_is_limited_per_hour_and_never_cached(client, admin_headers, admin_user, session_factory):
    from app.services.bitlocker_keys import MAX_REVEALS_PER_HOUR
    token, device_id = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    key_id = (await client.get(f"/api/v1/devices/{device_id}/bitlocker-keys", headers=admin_headers)).json()[0]["id"]
    url = f"/api/v1/devices/{device_id}/bitlocker-keys/{key_id}/reveal"

    r = await client.post(url, headers=admin_headers)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"

    async with session_factory() as s:
        for _ in range(MAX_REVEALS_PER_HOUR):
            s.add(AuditLog(org_id=admin_user.org_id, actor_id=admin_user.id,
                           action="device.bitlocker_key_reveal", target_type="device", target_id=device_id))
        await s.commit()
    assert (await client.post(url, headers=admin_headers)).status_code == 429


async def test_deleting_a_device_records_how_many_keys_went_with_it(client, admin_headers, session_factory):
    token, device_id = await _enroll(client, admin_headers)
    await _escrow(client, token, [KEY])
    assert (await client.delete(f"/api/v1/devices/{device_id}", headers=admin_headers)).status_code == 204
    async with session_factory() as s:
        entry = (await s.execute(select(AuditLog).where(AuditLog.action == "device.delete"))).scalar_one()
        assert entry.detail["bitlocker_keys_destroyed"] == 1
