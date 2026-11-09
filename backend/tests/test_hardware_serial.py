"""L5a — serial number + BIOS: placeholders never become serials, admin values never get
overwritten, and older agents never wipe what they sent at enrollment."""
import pytest
from sqlalchemy import select

from app.models import Asset, Device
from app.models.asset_event import AssetEvent
from app.services.hardware import clean_serial, normalize_vendor


@pytest.mark.parametrize("raw", [
    "To Be Filled By O.E.M.", "  default string ", "System Serial Number", "0000000000",
    "XXXXXXXX", "None", "N/A", "123456789", "", "  ", None, "ab",
])
def test_placeholders_are_not_serials(raw):
    assert clean_serial(raw) is None


def test_real_serial_is_kept_trimmed():
    assert clean_serial("  5CD1234XYZ ") == "5CD1234XYZ"


@pytest.mark.parametrize("raw, vendor", [
    ("Dell Inc.", "Dell"), ("HP", "HP"), ("Hewlett-Packard", "HP"), ("LENOVO", "Lenovo"),
    ("Microsoft Corporation", "Microsoft"), ("ASUSTeK COMPUTER INC.", "ASUS"),
    ("ASUS", "ASUS"), ("Micro-Star International Co., Ltd.", "MSI"),
    ("HPE", None), ("To Be Filled By O.E.M.", None), (None, None),
])
def test_vendor_normalisation(raw, vendor):
    assert normalize_vendor(raw) == vendor


PUSH = {
    "collected_at": "2026-11-09T10:00:00Z", "cpu_percent": 5.0, "ram_total_mb": 8192,
    "ram_used_mb": 2048, "disks": [{"drive": "C:", "total_gb": 100.0, "used_gb": 20.0, "free_gb": 80.0}],
}


async def _enroll(client, admin_headers, serial):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "SER-PC", "machine_id": "ser-1",
        "os_version": "Windows 11", "agent_version": "0.14.0", "serial_number": serial})
    assert r.status_code == 200, r.text
    return r.json()["device_token"]


async def _push(client, token, hardware):
    r = await client.post("/api/v1/agent/telemetry", json=dict(PUSH, hardware=hardware),
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201, 204), r.text


async def _device(session_factory):
    async with session_factory() as s:
        return (await s.execute(select(Device).where(Device.machine_id == "ser-1"))).scalar_one()


async def test_placeholder_at_enrollment_is_not_stored(client, admin_headers, session_factory):
    await _enroll(client, admin_headers, "To Be Filled By O.E.M.")
    assert (await _device(session_factory)).serial_number is None


async def test_hourly_push_corrects_and_old_agents_leave_alone(client, admin_headers, session_factory):
    token = await _enroll(client, admin_headers, "Default string")
    await _push(client, token, {"manufacturer": "Dell Inc.", "serial_number": "7HXK2Q3",
                                "bios_version": "1.18.0", "bios_release_date": "2024-03-01"})
    d = await _device(session_factory)
    assert (d.serial_number, d.bios_version, d.bios_release_date) == ("7HXK2Q3", "1.18.0", "2024-03-01")

    # An older agent's hardware block has no serial field at all — must not wipe it.
    await _push(client, token, {"manufacturer": "Dell Inc."})
    assert (await _device(session_factory)).serial_number == "7HXK2Q3"


async def test_linked_asset_empty_fields_filled_admin_values_kept(
        client, admin_headers, admin_user, session_factory):
    token = await _enroll(client, admin_headers, None)
    d = await _device(session_factory)
    async with session_factory() as s:
        s.add(Asset(org_id=admin_user.org_id, name="Asha's laptop", device_id=d.id,
                    model="Typed by admin"))
        await s.commit()

    await _push(client, token, {"manufacturer": "Dell Inc.", "model": "Latitude 5440",
                                "serial_number": "7HXK2Q3"})
    async with session_factory() as s:
        a = (await s.execute(select(Asset).where(Asset.device_id == d.id))).scalar_one()
        events = (await s.execute(select(AssetEvent).where(AssetEvent.asset_id == a.id))).scalars().all()
    assert (a.serial_number, a.manufacturer, a.model) == ("7HXK2Q3", "Dell Inc.", "Typed by admin")
    assert any("serial number" in (e.note or "") for e in events)

    # Second push: nothing left to fill, so no new history noise.
    await _push(client, token, {"manufacturer": "Dell Inc.", "model": "Latitude 5440",
                                "serial_number": "7HXK2Q3"})
    async with session_factory() as s:
        again = (await s.execute(select(AssetEvent).where(AssetEvent.asset_id == a.id))).scalars().all()
    assert len(again) == len(events)


async def test_assembled_pc_placeholders_never_reach_device_or_asset(
        client, admin_headers, admin_user, session_factory):
    token = await _enroll(client, admin_headers, "To Be Filled By O.E.M.")
    d = await _device(session_factory)
    async with session_factory() as s:
        s.add(Asset(org_id=admin_user.org_id, name="Reception desktop", device_id=d.id))
        await s.commit()
    oem = "To Be Filled By O.E.M."
    await _push(client, token, {"manufacturer": oem, "model": oem, "serial_number": oem})
    d = await _device(session_factory)
    async with session_factory() as s:
        a = (await s.execute(select(Asset).where(Asset.device_id == d.id))).scalar_one()
    assert (d.manufacturer, d.model, d.serial_number) == (None, None, None)
    assert (a.manufacturer, a.model, a.serial_number) == (None, None, None)
