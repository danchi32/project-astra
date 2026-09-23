"""The platform-operator remote-control toggle: enable provisions the org on the relay,
disable is only the entitlement, and the relay objects outlive a disable on purpose.

Enabling stands an org up on the relay (a device group + a scoped account). These tests stub
the relay call itself — the boundary being checked is the service's own logic around it
(when it provisions, when it does not, what it stores, what the entitlement ends up as), not
the MeshCentral wire protocol, which test_remote_control_api covers.
"""
import collections
import json
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.models import Organization, User
from app.services.entitlements import REMOTE_CONTROL
from app.services.invites import InviteService
from app.services.meshcentral import (
    REMOTE_CONTROL_MESH_RIGHTS,
    MeshCentralClient,
    MeshCentralError,
)

_PW = "Password12345"


async def _issue_invite(session_factory) -> str:
    async with session_factory() as session:
        _, raw = await InviteService(session).create(note="t", expires_in_days=30)
    return raw


async def _register(client, code: str, org: str, email: str):
    return await client.post("/api/v1/auth/register", json={"terms_accepted": True,
        "invite_code": code, "organization_name": org,
        "admin_name": f"{org} Admin", "admin_email": email, "admin_password": _PW,
    })


async def _promote(session_factory, email: str) -> None:
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()


async def _operator(client, session_factory) -> dict[str, str]:
    """A platform admin, with the Authorization header the platform routes want."""
    reg = await _register(client, await _issue_invite(session_factory), "Ops Co", "ops@ops.com")
    await _promote(session_factory, "ops@ops.com")
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _customer(client, session_factory, name="Customer Co", email="c@cust.com") -> uuid.UUID:
    await _register(client, await _issue_invite(session_factory), name, email)
    async with session_factory() as s:
        org = (await s.execute(select(Organization).where(Organization.name == name))).scalar_one()
    return org.id


async def _org(session_factory, org_id: uuid.UUID) -> Organization:
    async with session_factory() as s:
        return await s.get(Organization, org_id)


def _relay(monkeypatch):
    """Make MeshCentralClient() report itself configured without a real relay behind it."""
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "meshcentral_url", "https://relay.test", raising=False)
    monkeypatch.setattr(s, "meshcentral_user", "~t:test", raising=False)
    monkeypatch.setattr(s, "meshcentral_token", "test-token", raising=False)


def _stub_provision(monkeypatch) -> list[dict]:
    """Replace the relay round-trip with a recorder. Returns the list it appends a dict of
    kwargs to on each call, so a test can assert whether — and with what — it ran."""
    calls: list[dict] = []

    async def fake(self, *, mesh_name, user_slug, password, rights):
        calls.append({"mesh_name": mesh_name, "user_slug": user_slug,
                      "password": password, "rights": rights})
        return "mesh//provisioned", "user//" + user_slug

    monkeypatch.setattr(MeshCentralClient, "provision_scoped_access", fake)
    return calls


async def test_enabling_a_fresh_org_provisions_the_relay_and_grants_the_entitlement(
    client, session_factory, monkeypatch
):
    _relay(monkeypatch)
    calls = _stub_provision(monkeypatch)
    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["remote_control_active"] is True
    assert "remote_control" in body["entitlements"]

    # The relay was stood up exactly once, for this org's own scoped account. The slug is the
    # FULL org uuid — a truncated one would make two orgs able to collide onto one account.
    assert len(calls) == 1
    assert calls[0]["user_slug"] == f"astra-org-{org_id.hex}"

    org = await _org(session_factory, org_id)
    assert org.meshcentral_mesh_id == "mesh//provisioned"
    assert org.meshcentral_user_id == "user//" + calls[0]["user_slug"]
    assert org.entitlement_overrides[REMOTE_CONTROL] is True


async def test_enabling_an_already_provisioned_org_does_not_reprovision(
    client, session_factory, monkeypatch
):
    _relay(monkeypatch)
    calls = _stub_provision(monkeypatch)
    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    # Pre-provision it, and turn the entitlement off, as a disabled-but-stood-up org looks.
    async with session_factory() as s:
        o = await s.get(Organization, org_id)
        o.meshcentral_mesh_id = "mesh//already"
        o.meshcentral_user_id = "user//astra-org-already"
        o.entitlement_overrides = {REMOTE_CONTROL: False}
        await s.commit()

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 200, r.text
    assert r.json()["remote_control_active"] is True

    # Re-enable is instant: the relay is untouched and the existing ids are kept.
    assert calls == []
    org = await _org(session_factory, org_id)
    assert org.meshcentral_mesh_id == "mesh//already"
    assert org.meshcentral_user_id == "user//astra-org-already"


async def test_disabling_keeps_the_relay_objects_and_only_flips_the_entitlement(
    client, session_factory, monkeypatch
):
    _relay(monkeypatch)
    calls = _stub_provision(monkeypatch)
    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    async with session_factory() as s:
        o = await s.get(Organization, org_id)
        o.meshcentral_mesh_id = "mesh//keep"
        o.meshcentral_user_id = "user//astra-org-keep"
        o.entitlement_overrides = {REMOTE_CONTROL: True}
        await s.commit()

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["remote_control_active"] is False
    assert "remote_control" not in body["entitlements"]

    assert calls == []  # disable never touches the relay
    org = await _org(session_factory, org_id)
    # The group and account outlive the disable, so a re-enable is instant.
    assert org.meshcentral_mesh_id == "mesh//keep"
    assert org.meshcentral_user_id == "user//astra-org-keep"
    assert org.entitlement_overrides[REMOTE_CONTROL] is False


async def test_a_half_provisioned_org_is_refused_and_left_untouched(
    client, session_factory, monkeypatch
):
    _relay(monkeypatch)
    calls = _stub_provision(monkeypatch)
    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    # One of the two relay ids set — the state a human must reconcile, never auto-heal.
    async with session_factory() as s:
        o = await s.get(Organization, org_id)
        o.meshcentral_mesh_id = "mesh//orphan"
        o.meshcentral_user_id = None
        await s.commit()

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 400, r.text
    assert "half-provisioned" in r.json()["detail"].lower()

    # No second group created, and the entitlement was not granted on a failed enable.
    assert calls == []
    org = await _org(session_factory, org_id)
    assert org.meshcentral_mesh_id == "mesh//orphan"
    assert org.meshcentral_user_id is None
    assert REMOTE_CONTROL not in (org.entitlement_overrides or {})


async def test_a_relay_failure_does_not_grant_the_entitlement(
    client, session_factory, monkeypatch
):
    _relay(monkeypatch)
    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    async def boom(self, **kwargs):
        raise MeshCentralError("relay unreachable")

    monkeypatch.setattr(MeshCentralClient, "provision_scoped_access", boom)

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 400, r.text
    assert "relay" in r.json()["detail"].lower()

    org = await _org(session_factory, org_id)
    assert org.meshcentral_mesh_id is None
    assert org.meshcentral_user_id is None
    # The entitlement is only set once provisioning has succeeded.
    assert REMOTE_CONTROL not in (org.entitlement_overrides or {})


async def test_enabling_without_a_configured_relay_is_refused(
    client, session_factory, monkeypatch
):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "meshcentral_url", "", raising=False)
    monkeypatch.setattr(s, "meshcentral_user", "", raising=False)
    monkeypatch.setattr(s, "meshcentral_token", "", raising=False)

    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 400, r.text
    org = await _org(session_factory, org_id)
    assert org.meshcentral_mesh_id is None
    assert REMOTE_CONTROL not in (org.entitlement_overrides or {})


async def test_a_regular_admin_cannot_toggle_remote_control(client, session_factory, monkeypatch):
    _relay(monkeypatch)
    _stub_provision(monkeypatch)
    # A normal org admin, never promoted.
    reg = await _register(client, await _issue_invite(session_factory), "Reg Co", "reg@reg.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    org_id = await _customer(client, session_factory, name="Other Co", email="o@o.com")

    r = await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 403, r.text


async def test_toggling_a_missing_org_is_a_404(client, session_factory, monkeypatch):
    _relay(monkeypatch)
    _stub_provision(monkeypatch)
    headers = await _operator(client, session_factory)

    r = await client.post(f"/api/v1/platform/organizations/{uuid.uuid4()}/remote-control",
                          headers=headers, json={"enabled": True})
    assert r.status_code == 404, r.text


async def test_enabling_is_written_to_the_audit_trail(client, session_factory, monkeypatch):
    _relay(monkeypatch)
    _stub_provision(monkeypatch)
    headers = await _operator(client, session_factory)
    org_id = await _customer(client, session_factory)

    await client.post(f"/api/v1/platform/organizations/{org_id}/remote-control",
                      headers=headers, json={"enabled": True})

    from app.models import AuditLog

    async with session_factory() as s:
        rows = (await s.execute(select(AuditLog).where(AuditLog.org_id == org_id))).scalars().all()
    assert any(a.action == "org.remote_control.enable" for a in rows)


# ── The scoped account's rights and the relay wire protocol ───────────────────
#
# The tests above stub the relay entirely. These check the two security-critical details of the
# relay round-trip itself: the rights bitmask the scoped account gets, and the refusal to bind a
# viewer cookie to a pre-existing site-admin account.


def test_the_scoped_account_rights_are_desktop_only_and_cannot_pivot():
    # The exact mask matters: it is the cross-tenant boundary. remotecontrol(8) is the only
    # grant; terminal/files/AMT are denied; the group/user management bits that would let the
    # account reach other orgs' devices must be absent.
    assert REMOTE_CONTROL_MESH_RIGHTS == 8 | 512 | 1024 | 2048
    assert REMOTE_CONTROL_MESH_RIGHTS & 8          # REMOTECONTROL granted
    assert not REMOTE_CONTROL_MESH_RIGHTS & 2      # MANAGEUSERS withheld
    assert not REMOTE_CONTROL_MESH_RIGHTS & 4      # MANAGECOMPUTERS withheld
    assert not REMOTE_CONTROL_MESH_RIGHTS & 16     # AGENTCONSOLE withheld
    assert not REMOTE_CONTROL_MESH_RIGHTS & 131072  # REMOTECOMMAND withheld


class _FakeWS:
    """A control-channel socket that answers each command from a canned table. Every admin
    command echoes its own `action`, which is how `_await_result` matches a reply — so the fake
    just tags its response with the action it received."""

    def __init__(self, responses: dict[str, dict]):
        self._responses = responses
        self._out: collections.deque[str] = collections.deque()
        self.sent: list[dict] = []

    async def send(self, raw: str) -> None:
        msg = json.loads(raw)
        self.sent.append(msg)
        resp = dict(self._responses.get(msg["action"], {}))
        resp["action"] = msg["action"]
        self._out.append(json.dumps(resp))

    async def recv(self) -> str:
        return self._out.popleft()


def _with_fake_ws(monkeypatch, ws: _FakeWS) -> None:
    _relay(monkeypatch)

    @asynccontextmanager
    async def fake_connect(self):
        yield ws

    monkeypatch.setattr(MeshCentralClient, "connect", fake_connect)


async def test_provision_creates_group_account_and_grant(monkeypatch):
    ws = _FakeWS({
        "createmesh": {"meshid": "mesh//new", "result": "ok"},
        "adduser": {"result": "ok"},
        "addmeshuser": {"success": True},
    })
    _with_fake_ws(monkeypatch, ws)

    mesh_id, user_id = await MeshCentralClient().provision_scoped_access(
        mesh_name="ASTRA - Test", user_slug="astra-org-abc", password="Aa1!secret",
        rights=REMOTE_CONTROL_MESH_RIGHTS,
    )
    assert mesh_id == "mesh//new"
    assert user_id == "user//astra-org-abc"
    grant = next(m for m in ws.sent if m["action"] == "addmeshuser")
    assert grant["meshadmin"] == REMOTE_CONTROL_MESH_RIGHTS
    assert grant["meshid"] == "mesh//new"
    # A freshly created account is a normal user by construction — no siteadmin lookup needed.
    assert not any(m["action"] == "users" for m in ws.sent)


async def test_provision_refuses_to_adopt_a_preexisting_site_admin(monkeypatch):
    ws = _FakeWS({
        "createmesh": {"meshid": "mesh//new"},
        "adduser": {"result": "already exists"},
        "users": {"users": [{"_id": "user//astra-org-abc", "siteadmin": 0xFFFFFFFF}]},
        "addmeshuser": {"success": True},
    })
    _with_fake_ws(monkeypatch, ws)

    with pytest.raises(MeshCentralError, match="site admin"):
        await MeshCentralClient().provision_scoped_access(
            mesh_name="ASTRA - Test", user_slug="astra-org-abc", password="Aa1!secret",
            rights=REMOTE_CONTROL_MESH_RIGHTS,
        )
    # The group was NEVER granted to the admin account.
    assert not any(m["action"] == "addmeshuser" for m in ws.sent)


async def test_provision_adopts_a_preexisting_plain_account(monkeypatch):
    ws = _FakeWS({
        "createmesh": {"meshid": "mesh//new"},
        "adduser": {"result": "already exists"},
        "users": {"users": {"user//astra-org-abc": {"_id": "user//astra-org-abc", "siteadmin": 0}}},
        "addmeshuser": {"success": True},
    })
    _with_fake_ws(monkeypatch, ws)

    # A non-admin account of the same name (our own retry) is adopted and granted the group.
    mesh_id, user_id = await MeshCentralClient().provision_scoped_access(
        mesh_name="ASTRA - Test", user_slug="astra-org-abc", password="Aa1!secret",
        rights=REMOTE_CONTROL_MESH_RIGHTS,
    )
    assert (mesh_id, user_id) == ("mesh//new", "user//astra-org-abc")
    assert any(m["action"] == "addmeshuser" for m in ws.sent)
