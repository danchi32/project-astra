"""The one-click .exe installer.

Unlike the .zip, the exe is NOT generated per organization: the Inno Setup compiler
is Windows-only and this backend runs on Linux, so one prebuilt exe is served to
everyone. Three consequences are what these tests pin down — the enrollment
credential has to ride in the filename, that credential must therefore be an
expiring, revocable ticket rather than the org's permanent key, and an exe compiled
against a different backend must never be handed out, because its agents would enrol
somewhere else.
"""
import json
import re
from pathlib import Path

import pytest

from app.services import agent_installer

REPO = Path(__file__).resolve().parents[2]
ISS = REPO / "agent" / "install" / "AstraAgent.iss"
KEYPARSE_ISS = REPO / "agent" / "install" / "keyparse.iss"

# What the test settings report as this deployment's public URL.
TEST_SERVER_URL = "http://localhost:8000"


def _served_name(resp) -> str:
    match = re.search(r'filename="?([^";]+)"?', resp.headers["content-disposition"])
    assert match, resp.headers["content-disposition"]
    return match.group(1)


def _ticket(resp) -> str:
    name = _served_name(resp)
    assert name.startswith("AstraAgent-Setup-") and name.endswith(".exe"), name
    return name[len("AstraAgent-Setup-") : -len(".exe")]


async def _enroll(client, credential, machine_id):
    return await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": credential, "hostname": machine_id, "machine_id": machine_id,
        "os_version": "Windows 11", "agent_version": "0.8.2"})


@pytest.fixture
def bundled_exe(tmp_path, monkeypatch):
    """Stand in for a build whose compiled-in backend matches this deployment."""
    exe = tmp_path / "AstraAgent-Setup.exe"
    exe.write_bytes(b"MZ fake installer payload")
    manifest = tmp_path / "AstraAgent-Setup.json"
    manifest.write_text(json.dumps({"agent_version": "9.9.9", "server_url": TEST_SERVER_URL}))
    monkeypatch.setattr(agent_installer, "SETUP_EXE", exe)
    monkeypatch.setattr(agent_installer, "SETUP_MANIFEST", manifest)
    return exe


async def test_filename_carries_a_ticket_that_can_enrol(client, admin_headers, bundled_exe):
    """The filename is the delivery mechanism for the credential, not decoration."""
    resp = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.content == bundled_exe.read_bytes()

    enrolled = await _enroll(client, _ticket(resp), "PC-EXE")
    assert enrolled.status_code == 200, enrolled.text
    assert "device_token" in enrolled.json()


async def test_the_permanent_key_never_appears_in_a_filename(client, admin_headers, bundled_exe):
    """The whole point of the ticket. A filename is exposed in ways a permanent,
    unexpiring, org-wide secret should not be — and rotating that key to recover from
    a leak would break every .zip installer already distributed."""
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    resp = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)

    assert key not in _served_name(resp)
    assert _ticket(resp) != key
    # Short enough to be a sane filename, long enough to be unguessable.
    assert 16 <= len(_ticket(resp)) < len(key)


async def test_each_download_gets_its_own_ticket(client, admin_headers, bundled_exe):
    """Only the hash is stored, so an earlier ticket cannot be reissued — and reusing
    one would mean a single leak invalidates every download at once."""
    first = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    second = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)

    assert _ticket(first) != _ticket(second)
    assert first.content == second.content, "the exe itself must stay byte-identical"

    # Both still work: re-downloading must not silently kill copies already handed out.
    assert (await _enroll(client, _ticket(first), "PC-A")).status_code == 200
    assert (await _enroll(client, _ticket(second), "PC-B")).status_code == 200


async def test_revoking_kills_exe_installers_but_not_the_zip(client, admin_headers, bundled_exe):
    """Separating the two credentials is what makes this possible: a leaked .exe no
    longer forces a key rotation that would break every .zip as well."""
    resp = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    ticket = _ticket(resp)
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]

    revoked = await client.post("/api/v1/devices/exe-installer/revoke", headers=admin_headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked"] == 1

    assert (await _enroll(client, ticket, "PC-DEAD")).status_code == 401
    assert (await _enroll(client, key, "PC-ZIP")).status_code == 200, "the .zip must be unaffected"


async def test_revoking_with_nothing_outstanding_is_harmless(client, admin_headers, bundled_exe):
    resp = await client.post("/api/v1/devices/exe-installer/revoke", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["revoked"] == 0


async def test_exe_built_for_another_backend_is_refused(client, admin_headers, tmp_path, monkeypatch):
    """An exe carries its backend URL compiled in. Serving one built elsewhere would
    quietly enrol this customer's machines into a different deployment."""
    exe = tmp_path / "AstraAgent-Setup.exe"
    exe.write_bytes(b"MZ")
    manifest = tmp_path / "AstraAgent-Setup.json"
    manifest.write_text(json.dumps({"server_url": "https://someone-elses-backend.example"}))
    monkeypatch.setattr(agent_installer, "SETUP_EXE", exe)
    monkeypatch.setattr(agent_installer, "SETUP_MANIFEST", manifest)

    installer = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()
    assert installer["exe_available"] is False, "the portal must not offer an unusable exe"

    resp = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    assert resp.status_code == 503
    assert "someone-elses-backend.example" in resp.json()["detail"]


async def test_missing_exe_degrades_to_the_zip(client, admin_headers, tmp_path, monkeypatch):
    """A deployment that never bundled the exe still offers the zip; it does not 500."""
    monkeypatch.setattr(agent_installer, "SETUP_EXE", tmp_path / "absent.exe")
    monkeypatch.setattr(agent_installer, "SETUP_MANIFEST", tmp_path / "absent.json")

    installer = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()
    assert installer["exe_available"] is False
    assert installer["exe_ticket_days"] is None
    assert installer["enrollment_key"]  # the rest of the page still works

    assert (await client.post("/api/v1/devices/exe-installer", headers=admin_headers)).status_code == 503
    assert (await client.post("/api/v1/devices/offline-installer", headers=admin_headers)).status_code == 201


async def test_installer_page_advertises_the_ticket_lifetime(client, admin_headers, bundled_exe):
    """An admin distributing installers needs to know they expire before they do."""
    body = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()
    assert body["exe_available"] is True
    assert body["exe_ticket_days"] == 7  # the org default
    assert "exe_filename" not in body, "the name only exists once a ticket is minted"


async def test_exe_requires_admin(client, user_headers, bundled_exe):
    assert (await client.post("/api/v1/devices/exe-installer", headers=user_headers)).status_code == 403
    assert (await client.post("/api/v1/devices/exe-installer/revoke", headers=user_headers)).status_code == 403


async def test_exe_requires_auth(client, bundled_exe):
    assert (await client.post("/api/v1/devices/exe-installer")).status_code == 401


def test_filename_prefix_matches_the_installer_script():
    """The exe parses the credential back out of its own filename using a prefix defined
    in AstraAgent.iss. If these two ever drift, every downloaded installer would silently
    stop finding its ticket and fall back to prompting — so pin them together here."""
    match = re.search(r'#define\s+KeyPrefix\s+"([^"]+)"', ISS.read_text(encoding="utf-8"))
    assert match, f"KeyPrefix not found in {ISS}"
    assert match.group(1) == agent_installer.SETUP_EXE_PREFIX


def test_installer_accepts_the_ticket_length_we_actually_issue():
    """The installer rejects anything outside a length band before using it. A ticket
    shorter than that band would be discarded on every machine, and the failure would
    look like a rename rather than a server-side change — so check the band covers what
    generate_installer_ticket produces."""
    from app.core.security import generate_installer_ticket

    match = re.search(
        r"if \(Length\(S\) < (\d+)\) or \(Length\(S\) > (\d+)\) then",
        KEYPARSE_ISS.read_text(encoding="utf-8"),
    )
    assert match, f"length bound not found in {KEYPARSE_ISS}"
    low, high = int(match.group(1)), int(match.group(2))
    assert low <= len(generate_installer_ticket()) <= high
