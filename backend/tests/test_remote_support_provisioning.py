"""Whether a device is told to install the remote-support agent at all.

Nothing about remote support ships in the ASTRA installer. A device asks, and only
installs the relay agent if the answer says so — which is what keeps a remote-access
executable off the machines of every customer who never bought remote control.

Three conditions must ALL hold before the answer is yes, and they fail differently:
a relay configured on this deployment, the org's plan including the feature, and an
operator having created a device group for that org on the relay.
"""

from app.core.security import hash_opaque_token
from app.models import Device, Organization
from app.models.base import utcnow
from app.services.entitlements import REMOTE_CONTROL

# The org stores the id WITH its "mesh//" prefix — that is what the operator job
# writes and what production holds. The download URL must carry the BARE id, because
# the relay's /meshagents endpoint answers 401 for the prefixed form. Storing the
# bare id here (as this test first did) hid that entirely.
MESH_BARE = "pw0O8BcmHXFUdvuA6SgKIZQsA84rajqeYSvsAYOAFfRa1iwt5oqf5F3Nryse57sP"
MESH = "mesh//" + MESH_BARE


async def _device_token(session_factory, org, machine="rs-1") -> str:
    async with session_factory() as s:
        s.add(Device(
            org_id=org.id, hostname="RS-PC", machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
        ))
        await s.commit()
    return f"tok-{machine}"


async def _configure(session_factory, org, *, entitled: bool, mesh: str | None):
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.entitlement_overrides = {REMOTE_CONTROL: entitled}
        o.meshcentral_mesh_id = mesh
        await s.commit()


async def _ask(client, token):
    r = await client.get("/api/v1/agent/remote-support",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


async def test_a_device_with_no_relay_on_this_deployment_is_told_no(
    client, session_factory, org
):
    """Most deployments. conftest forces the relay settings empty, so this is the
    default answer and it must be a clean "no" rather than an error."""
    await _configure(session_factory, org, entitled=True, mesh=MESH)
    plan = await _ask(client, await _device_token(session_factory, org, "rs-1"))
    assert plan["enabled"] is False
    assert plan["download_url"] is None


async def test_an_org_without_the_feature_is_told_no(
    client, session_factory, org, monkeypatch
):
    _relay(monkeypatch)
    await _configure(session_factory, org, entitled=False, mesh=MESH)
    plan = await _ask(client, await _device_token(session_factory, org, "rs-2"))
    assert plan["enabled"] is False


async def test_an_entitled_org_with_no_device_group_is_told_no(
    client, session_factory, org, monkeypatch
):
    """The belt-and-braces half. The entitlement is a commercial decision anyone who can
    edit an org may grant; this one takes somebody having actually created a group on the
    relay. A mis-granted entitlement must not be enough to push a remote-access agent
    onto a fleet."""
    _relay(monkeypatch)
    await _configure(session_factory, org, entitled=True, mesh=None)
    plan = await _ask(client, await _device_token(session_factory, org, "rs-3"))
    assert plan["enabled"] is False


async def test_all_three_together_produce_a_download(
    client, session_factory, org, monkeypatch
):
    _relay(monkeypatch)
    await _configure(session_factory, org, entitled=True, mesh=MESH)
    plan = await _ask(client, await _device_token(session_factory, org, "rs-4"))

    assert plan["enabled"] is True
    # One file, with the server URL, group and certificate hash already inside it — so
    # there is nothing to place beside it and nothing for the device to configure.
    url = plan["download_url"]
    assert url.startswith("https://relay.test/meshagents?id=4")
    # The bare id, and NOT the prefix in any form — this is the 401 regression.
    assert MESH_BARE in url
    assert "mesh//" not in url and "mesh%2F%2F" not in url and "mesh%2f%2f" not in url
    # Sent rather than hardcoded at both ends: it is the Windows service name AND the
    # registry key the node id is read from, so the two must not drift.
    assert plan["service_name"] == "AstraRemoteSupport"


async def test_each_org_is_sent_only_its_own_group(
    client, session_factory, org, other_org, monkeypatch
):
    """The isolation that matters. Two customers on one relay must never be handed each
    other's group — an agent in the wrong group is reachable by the wrong people."""
    _relay(monkeypatch)
    theirs_bare = "OTHERMESHIDoooooooooooooooooooooooooooooooooooooooooooooooooooo"
    theirs = "mesh//" + theirs_bare
    await _configure(session_factory, org, entitled=True, mesh=MESH)
    await _configure(session_factory, other_org, entitled=True, mesh=theirs)

    mine = await _ask(client, await _device_token(session_factory, org, "rs-5"))
    yours = await _ask(client, await _device_token(session_factory, other_org, "rs-6"))

    assert MESH_BARE in mine["download_url"] and theirs_bare not in mine["download_url"]
    assert theirs_bare in yours["download_url"] and MESH_BARE not in yours["download_url"]


def _relay(monkeypatch):
    """Point the client at a relay that does not exist. Nothing here connects to one —
    the endpoint only composes a URL — and a test that could reach a real relay is the
    hazard conftest already guards against."""
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "meshcentral_url", "https://relay.test", raising=False)
    monkeypatch.setattr(s, "meshcentral_user", "~t:test", raising=False)
    monkeypatch.setattr(s, "meshcentral_token", "test-token", raising=False)
