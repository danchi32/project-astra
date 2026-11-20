"""Static agent downloads.

The uninstaller zip is baked into the backend image at build time
(backend/downloads/agent-uninstaller.zip -> /app/downloads/) so it survives every redeploy.

There used to be an `/agent` route here serving a ~34 MB self-contained agent build for an
online installer that fetched it at install time. Both are gone: the agent ships as the
portable bundle (see app/services/agent_installer.py), the portal never offered the online
route, and the blob cost 34 MB in every image for a path nothing used.
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services.agent_installer import UNINSTALLER_ZIP
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/downloads", tags=["downloads"])

# SAVIO Guard for "Load unpacked", until it is listed in the browsers' stores. Built by
# extension/pack.py and committed; test_downloads.py fails when it no longer matches extension/.
EXTENSION_ZIP = UNINSTALLER_ZIP.parent / "savio-guard-extension.zip"


@router.get("/extension", summary="Download the SAVIO Guard browser extension (zip, for Load unpacked)")
async def download_extension() -> FileResponse:
    # Public like the uninstaller: the same code is in the public repository, with no org data in it.
    if not EXTENSION_ZIP.is_file():
        raise NotFoundError("The extension is not bundled with this deployment.")
    return FileResponse(EXTENSION_ZIP, media_type="application/zip", filename="savio-guard-extension.zip")


@router.get("/uninstaller", summary="Download the SAVIO agent uninstaller (zip)")
async def download_uninstaller() -> FileResponse:
    # Org-agnostic: no secrets or per-org data, so it's a plain static download.
    if not UNINSTALLER_ZIP.is_file():
        raise NotFoundError(
            "Uninstaller is not bundled with this deployment. "
            "Commit backend/downloads/agent-uninstaller.zip and redeploy."
        )
    return FileResponse(
        UNINSTALLER_ZIP,
        media_type="application/zip",
        filename="AstraAgent-Uninstaller.zip",
    )
