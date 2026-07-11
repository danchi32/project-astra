"""Agent and asset downloads."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("/agent", summary="Download ASTRA Windows agent installer")
async def download_agent() -> FileResponse:
    """Download the latest ASTRA Windows agent (dist.zip).

    The agent file is served from the backend's downloads directory.
    Place agent/install/dist.zip at C:\app\downloads\agent.zip on deployment.
    """
    agent_path = Path("/app/downloads/agent.zip")

    if not agent_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Agent installer not found. Upload dist.zip to /app/downloads/agent.zip on the server."
        )

    return FileResponse(
        agent_path,
        media_type="application/zip",
        filename="astra-agent-v1.0.0.zip"
    )
