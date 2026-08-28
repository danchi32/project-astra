"""Stage everything AstraAgent.iss compiles into the single-file .exe installer.

Run by Build-Installer.ps1; there is no reason to run it by hand.

The point of this script is that the .exe must not carry its own copy of the
install logic. The canonical installer script lives in
``backend/app/services/agent_installer.py`` (it is what the .zip download is built
from), and the agent binaries live in ``backend/downloads/agent-portable.zip`` (the
exact bytes that download serves). Both are pulled from there, so the .exe and the
.zip install the same agent the same way, and a fix to either automatically reaches
both on the next build.

The one thing the .exe cannot take from the backend is the enrollment key: the exe
is compiled once and served byte-identically to every organization, so the key
arrives in its filename at download time instead. The staged script therefore has
an empty key baked in — AstraAgent.iss always passes ``-EnrollmentToken`` explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER_DIR = REPO / "agent" / "install"
PAYLOAD_DIR = INSTALLER_DIR / "payload"
PORTABLE_ZIP = REPO / "backend" / "downloads" / "agent-portable.zip"
UNINSTALL_SCRIPT = INSTALLER_DIR / "Uninstall-AstraAgent.ps1"
# The tray chat's icon, reused for the installer and the Add/Remove Programs entry so
# ASTRA looks like one product wherever Windows shows it.
BRAND_ICON = REPO / "agent" / "src" / "AstraAgent.Tray" / "astra.ico"
# The licence the wizard makes the installer accept before anything is written. Staged
# like the icon and the uninstaller: payload/ is wiped and rebuilt on every run, so the
# tracked source lives here and is copied in.
EULA = INSTALLER_DIR / "EULA.txt"
# The single source of truth for the agent version; both csprojs inherit it from here.
VERSION_PROPS = REPO / "agent" / "src" / "Directory.Build.props"
AGENT_INSTALLER_MODULE = REPO / "backend" / "app" / "services" / "agent_installer.py"

DEFAULT_SERVER_URL = "https://api.astra.technomateai.com"


def load_install_script_builder():
    """Import agent_installer.py straight off disk.

    Deliberately not ``from app.services.agent_installer import ...``: that would
    execute the app package's __init__ chain and drag the backend's dependencies
    into what is otherwise a plain packaging step. The module itself imports only
    the standard library, so loading it in isolation is safe.
    """
    spec = importlib.util.spec_from_file_location("_astra_agent_installer", AGENT_INSTALLER_MODULE)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"Could not load {AGENT_INSTALLER_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_portable_install_script


def agent_version() -> str:
    match = re.search(r"<Version>([^<]+)</Version>", VERSION_PROPS.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError(f"No <Version> in {VERSION_PROPS}")
    return match.group(1).strip()


def stage_binaries() -> dict[str, int]:
    """Unpack dist-fd/ and dist-tray/ out of the shipped portable bundle."""
    if not PORTABLE_ZIP.is_file():
        raise SystemExit(
            f"Missing {PORTABLE_ZIP}.\n"
            "That bundle is the agent payload both downloads share; build it first."
        )

    counts = {"dist-fd": 0, "dist-tray": 0}
    with zipfile.ZipFile(PORTABLE_ZIP) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            top = name.split("/", 1)[0]
            if top not in counts:
                raise SystemExit(f"Unexpected entry in the portable bundle: {name}")
            target = PAYLOAD_DIR / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            counts[top] += 1

    for folder, count in counts.items():
        if count == 0:
            raise SystemExit(f"The portable bundle contains no {folder}/ files.")
    if not (PAYLOAD_DIR / "dist-fd" / "AstraAgent.Service.dll").is_file():
        raise SystemExit("dist-fd/AstraAgent.Service.dll missing from the portable bundle.")
    if not (PAYLOAD_DIR / "dist-tray" / "AstraAgent.Tray.dll").is_file():
        raise SystemExit("dist-tray/AstraAgent.Tray.dll missing from the portable bundle.")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help=(
            "Backend the installer points at. Compiled in, so it must match the "
            "public_api_url of the deployment that serves the exe."
        ),
    )
    args = parser.parse_args()
    server_url = args.server_url.rstrip("/")

    if PAYLOAD_DIR.exists():
        shutil.rmtree(PAYLOAD_DIR)
    PAYLOAD_DIR.mkdir(parents=True)

    counts = stage_binaries()

    build_script = load_install_script_builder()
    # An empty key on purpose — AstraAgent.iss passes the real one on the command
    # line. Baking a placeholder here would risk it being used if that ever broke.
    (PAYLOAD_DIR / "Install-AstraAgent.ps1").write_text(
        build_script(server_url=server_url, enrollment_token="", backend_ip=""),
        encoding="utf-8",
    )

    if not UNINSTALL_SCRIPT.is_file():
        raise SystemExit(f"Missing {UNINSTALL_SCRIPT}")
    shutil.copy2(UNINSTALL_SCRIPT, PAYLOAD_DIR / "Uninstall-AstraAgent.ps1")

    if not BRAND_ICON.is_file():
        raise SystemExit(f"Missing {BRAND_ICON}")
    shutil.copy2(BRAND_ICON, PAYLOAD_DIR / "astra.ico")

    # Hard failure, not a warning: AstraAgent.iss names this as its LicenseFile, so a
    # missing EULA would stop the compile anyway — better to say why here.
    if not EULA.is_file():
        raise SystemExit(f"Missing {EULA}")
    shutil.copy2(EULA, PAYLOAD_DIR / "EULA.txt")

    version = agent_version()
    # The exe is byte-identical for every organization, so the backend it points at
    # is fixed at build time. The backend reads this sidecar and refuses to offer
    # the exe when the URL is not its own, rather than handing out an installer
    # whose agents would enrol somewhere else.
    (INSTALLER_DIR / "payload-manifest.json").write_text(
        json.dumps(
            {
                "agent_version": version,
                "server_url": server_url,
                "portable_zip_sha256": hashlib.sha256(PORTABLE_ZIP.read_bytes()).hexdigest(),
                "file_counts": counts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Staged agent {version} -> {PAYLOAD_DIR}")
    print(f"  dist-fd   : {counts['dist-fd']} files")
    print(f"  dist-tray : {counts['dist-tray']} files")
    print(f"  server    : {server_url}")
    # Build-Installer.ps1 reads this to pass /DAgentVersion to ISCC.
    print(f"AGENT_VERSION={version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
