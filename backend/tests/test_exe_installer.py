"""The one-click .exe installer.

Unlike the .zip, the exe is NOT generated per organization: the Inno Setup compiler
is Windows-only and this backend runs on Linux, so one prebuilt exe is served to
everyone. Two consequences are what these tests pin down — the per-org enrollment key
has to ride in the filename, and an exe compiled against a different backend must
never be handed out, because its agents would enrol somewhere else.
"""
import json
import re
from pathlib import Path

import pytest

from app.services import agent_installer

REPO = Path(__file__).resolve().parents[2]
ISS = REPO / "agent" / "install" / "AstraAgent.iss"

# What the test settings report as this deployment's public URL.
TEST_SERVER_URL = "http://localhost:8000"


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


async def test_exe_is_served_under_a_filename_carrying_the_key(
    client, admin_headers, bundled_exe
):
    """The filename is the delivery mechanism for the key, not decoration."""
    installer = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()
    key = installer["enrollment_key"]
    assert installer["exe_filename"] == f"AstraAgent-Setup-{key}.exe"

    resp = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.content == bundled_exe.read_bytes()
    assert f"AstraAgent-Setup-{key}.exe" in resp.headers["content-disposition"]


async def test_every_org_gets_the_same_bytes_under_a_different_name(
    client, admin_headers, bundled_exe
):
    """Byte-identical output is the property that lets this be signed later."""
    first = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    await client.post("/api/v1/devices/enrollment-key/rotate", headers=admin_headers)
    second = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)

    assert first.content == second.content
    assert first.headers["content-disposition"] != second.headers["content-disposition"]


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
    assert installer["exe_filename"] is None, "the portal must not offer an unusable exe"

    resp = await client.post("/api/v1/devices/exe-installer", headers=admin_headers)
    assert resp.status_code == 503
    assert "someone-elses-backend.example" in resp.json()["detail"]


async def test_missing_exe_degrades_to_the_zip(client, admin_headers, tmp_path, monkeypatch):
    """A deployment that never bundled the exe still offers the zip; it does not 500."""
    monkeypatch.setattr(agent_installer, "SETUP_EXE", tmp_path / "absent.exe")
    monkeypatch.setattr(agent_installer, "SETUP_MANIFEST", tmp_path / "absent.json")

    installer = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()
    assert installer["exe_filename"] is None
    assert installer["enrollment_key"]  # the rest of the page still works

    assert (await client.post("/api/v1/devices/exe-installer", headers=admin_headers)).status_code == 503
    assert (await client.post("/api/v1/devices/offline-installer", headers=admin_headers)).status_code == 201


async def test_exe_requires_admin(client, user_headers, bundled_exe):
    assert (await client.post("/api/v1/devices/exe-installer", headers=user_headers)).status_code == 403


async def test_exe_requires_auth(client, bundled_exe):
    assert (await client.post("/api/v1/devices/exe-installer")).status_code == 401


def test_filename_prefix_matches_the_installer_script():
    """The exe parses the key back out of its own filename using a prefix defined in
    AstraAgent.iss. If these two ever drift, every downloaded installer would silently
    stop finding its key and fall back to prompting — so pin them together here."""
    match = re.search(r'#define\s+KeyPrefix\s+"([^"]+)"', ISS.read_text(encoding="utf-8"))
    assert match, f"KeyPrefix not found in {ISS}"
    assert match.group(1) == agent_installer.SETUP_EXE_PREFIX
