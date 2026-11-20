"""The public agent-download endpoints."""


async def test_uninstaller_is_downloadable(client):
    # Org-agnostic, public (no auth) — an admin can grab it separately from the installer.
    response = await client.get("/api/v1/downloads/uninstaller")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert "AstraAgent-Uninstaller.zip" in response.headers.get("content-disposition", "")
    # It's a real zip (PK magic) and non-trivial.
    assert response.content[:2] == b"PK"
    assert len(response.content) > 200


async def test_extension_is_downloadable(client):
    response = await client.get("/api/v1/downloads/extension")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert "savio-guard-extension.zip" in response.headers.get("content-disposition", "")


def test_extension_zip_matches_the_source():
    """The served zip is what extension/ holds now: rerun `python extension/pack.py` after changing it."""
    import importlib.util
    import io
    import zipfile
    from pathlib import Path

    from app.api.v1.downloads import EXTENSION_ZIP

    spec = importlib.util.spec_from_file_location("pack", Path(__file__).resolve().parents[2] / "extension" / "pack.py")
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)
    want = {f"{pack.FOLDER}/{f.name}": pack.content(f) for f in pack.files()}
    with zipfile.ZipFile(io.BytesIO(EXTENSION_ZIP.read_bytes())) as z:
        have = {n: z.read(n) for n in z.namelist()}
    assert have == want, "backend/downloads/savio-guard-extension.zip is stale: run python extension/pack.py"
    assert '"key"' in want[f"{pack.FOLDER}/manifest.json"].decode()  # the fixed ID survives packing
