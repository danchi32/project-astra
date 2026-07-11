"""Agent binary download.

The published agent zip is baked into the backend image at build time
(backend/downloads/agent.zip -> /app/downloads/agent.zip) so it survives every
redeploy. The generated installer script (see app/services/agent_installer.py)
fetches it from here, so an admin only ever downloads one small script.
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/downloads", tags=["downloads"])

# downloads.py lives at <app_root>/app/api/v1/downloads.py; the binary sits at
# <app_root>/downloads/agent.zip. Resolve relative to this file so it works
# regardless of the container's working directory.
AGENT_ZIP = Path(__file__).resolve().parents[3] / "downloads" / "agent.zip"


@router.get("/agent", summary="Download the ASTRA Windows agent binary (zip)")
async def download_agent() -> FileResponse:
    if not AGENT_ZIP.is_file():
        raise NotFoundError(
            "Agent binary is not bundled with this deployment. "
            "Commit backend/downloads/agent.zip and redeploy."
        )
    return FileResponse(
        AGENT_ZIP,
        media_type="application/zip",
        filename="astra-agent.zip",
    )
