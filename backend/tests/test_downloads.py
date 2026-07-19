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
