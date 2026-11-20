"""Pack SAVIO Guard for "Load unpacked" into backend/downloads/savio-guard-extension.zip, which the
backend serves. Rerun after any change here: test_downloads.py fails while the zip is stale.
Everything sits under one folder, savio-guard/, which is the folder an admin picks in the browser.
Usage: python extension/pack.py"""
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "backend" / "downloads" / "savio-guard-extension.zip"
FOLDER = "savio-guard"


def files() -> list[Path]:
    """What the browser loads: the manifest, its schema and the scripts. Not the tests or tooling."""
    return sorted([HERE / "manifest.json", HERE / "managed_schema.json", *HERE.glob("*.js")])


def content(f: Path) -> bytes:
    """LF endings whatever the checkout did, so a Windows build and CI's Linux one agree."""
    return f.read_bytes().replace(b"\r\n", b"\n")


if __name__ == "__main__":
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files():
            # A fixed date, so the zip only changes when a file does.
            z.writestr(zipfile.ZipInfo(f"{FOLDER}/{f.name}", (2026, 1, 1, 0, 0, 0)), content(f),
                       zipfile.ZIP_DEFLATED)
    print("wrote", OUT, len(files()), "files")
