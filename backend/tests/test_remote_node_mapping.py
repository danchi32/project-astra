"""The agent tells ASTRA which node it is, and ASTRA believes it — carefully.

The node id comes from the relay agent's own registry key, which the ASTRA agent reads and
reports on every heartbeat. Everything here is about the two ways that can go wrong: a
silence erasing a working mapping, and a bad value reaching a URL that opens somebody's
screen.

The literal below is a real node id, copied from a live relay during the spike. Made-up
values would not have caught the `$` and `@` the relay's own encoding uses.
"""
import pytest

from app.models import Device

# Verified end to end: this machine's registry held the value without the prefix, and the
# relay's record for it was exactly "node//" + that. The prefix is the agent's to add.
REAL_NODE_ID = "node//VbEogKWjWXu0oeinl$PohxBPtn$ha9@qk$gzrCdB7l7sKf1zVAjFkDYIXnefOetW"


async def _enroll(client, admin_headers, machine="rn-1") -> str:
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)
           ).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "RN-PC", "machine_id": machine,
        "os_version": "Windows 11", "agent_version": "0.6.4"})
    assert r.status_code in (200, 201), r.text
    return r.json()["device_token"]


async def _beat(client, token, **extra):
    return await client.post(
        "/api/v1/agent/heartbeat",
        json={"agent_version": "0.6.4", "include_tasks": False, **extra},
        headers={"Authorization": f"Bearer {token}"})


async def _device(session_factory, machine="rn-1") -> Device:
    from sqlalchemy import select
    async with session_factory() as s:
        return (await s.execute(
            select(Device).where(Device.machine_id == machine))).scalars().first()


async def test_the_agent_reports_its_node_id_on_a_beat(
    client, session_factory, admin_headers
):
    token = await _enroll(client, admin_headers, "rn-1")
    assert (await _beat(client, token, remote_node_id=REAL_NODE_ID)).status_code == 200

    device = await _device(session_factory, "rn-1")
    assert device.meshcentral_node_id == REAL_NODE_ID


async def test_a_reinstalled_relay_agent_corrects_the_mapping(
    client, session_factory, admin_headers
):
    """The reason this rides on every beat instead of enrollment.

    Reinstalling the relay agent gives the machine a new node id. A mapping still pointing
    at the old one would take remote control down for that device, silently, until somebody
    went looking for why.
    """
    token = await _enroll(client, admin_headers, "rn-2")
    await _beat(client, token, remote_node_id=REAL_NODE_ID)

    new_id = "node//SX8JJo0bFTbdiadooHfDCJKO2KDRMtGNervDDhBof9snhWja3sjHZC4tbF9Zrl5M"
    await _beat(client, token, remote_node_id=new_id)

    device = await _device(session_factory, "rn-2")
    assert device.meshcentral_node_id == new_id


@pytest.mark.parametrize("omitted", [{}, {"remote_node_id": None}])
async def test_silence_never_erases_a_working_mapping(
    client, session_factory, admin_headers, omitted
):
    """An older agent sends nothing; an agent whose registry read failed sends null. Both
    must leave the mapping alone — erasing it would break remote support for that device
    with nothing in the record to explain why."""
    machine = f"rn-3{len(omitted)}"
    token = await _enroll(client, admin_headers, machine)
    await _beat(client, token, remote_node_id=REAL_NODE_ID)

    assert (await _beat(client, token, **omitted)).status_code == 200

    device = await _device(session_factory, machine)
    assert device.meshcentral_node_id == REAL_NODE_ID


@pytest.mark.parametrize("bad", [
    "VbEogKWjWXu0oeinl",                      # no prefix — the agent's job to add it
    "mesh//pw0O8BcmHXFUdvuA6SgKIZQsA84",      # a group id, not a device
    "node//../../etc/passwd",
    "node//abc?login=stolen",
    "node//abc&gotonode=someone-else",
    "node//<script>alert(1)</script>",
    "node//",
    "http://evil.example.com/",
])
async def test_a_malformed_node_id_is_refused_rather_than_stored(
    client, session_factory, admin_headers, bad
):
    """This value goes straight into a URL that opens somebody's screen.

    Length-checking it would not be enough: `&gotonode=` in the middle of an accepted value
    would let a device redirect its own viewer link at a different machine. So the shape is
    validated, and anything that is not a node id is a 422 — the device keeps whatever
    mapping it already had.
    """
    token = await _enroll(client, admin_headers, f"rn-bad{abs(hash(bad)) % 10000}")
    machine = f"rn-bad{abs(hash(bad)) % 10000}"
    await _beat(client, token, remote_node_id=REAL_NODE_ID)

    r = await _beat(client, token, remote_node_id=bad)
    assert r.status_code == 422, (bad, r.status_code, r.text)

    device = await _device(session_factory, machine)
    assert device.meshcentral_node_id == REAL_NODE_ID


async def test_a_device_that_never_reports_one_has_none(
    client, session_factory, admin_headers
):
    """Most devices, for now. No relay agent installed means no remote control, and the
    absence has to be readable as absence rather than as an empty string."""
    token = await _enroll(client, admin_headers, "rn-4")
    await _beat(client, token)
    assert (await _device(session_factory, "rn-4")).meshcentral_node_id is None
