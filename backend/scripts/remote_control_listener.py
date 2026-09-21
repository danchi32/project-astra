"""Entry point for the remote-control listener service.

This is a SERVICE, not a job. It serves no HTTP traffic — it holds one connection to the
MeshCentral relay and writes what the relay reports into ASTRA's own record.

Deploy it as its own Cloud Run service with min-instances=1 and MAX-INSTANCES=1. The max
is the part that matters: the relay pushes each event to everyone listening, so a second
instance means every consent, every disconnect and every audit entry happens twice.

    gcloud run deploy astra-remote-listener \
      --image "$IMAGE" --region "$REGION" \
      --min-instances 1 --max-instances 1 --no-cpu-throttling \
      --command python --args scripts/remote_control_listener.py \
      --set-secrets ASTRA_DATABASE_URL=...,ASTRA_MESHCENTRAL_TOKEN=...

`--no-cpu-throttling` is not optional: without it Cloud Run suspends the CPU between
requests, and a service whose whole job is to wait on a socket never gets a request.

Locally, with the relay running on this machine:

    ASTRA_DATABASE_URL=sqlite+aiosqlite:///./astra-demo.db \
        backend/.venv/Scripts/python.exe backend/scripts/remote_control_listener.py
"""
import asyncio
import logging
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
# Settings reads `.env` relative to the working directory — see seed_builtin_assistant.py
# for the full story. Same fix, same reason.
os.chdir(BACKEND_DIR)

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.meshcentral import MeshCentralClient  # noqa: E402
from app.services.remote_control_listener import RemoteControlListener  # noqa: E402


async def main() -> int:
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("astra.remote-listener")

    client = MeshCentralClient()
    if not client.configured:
        # Not an error. Most deployments have no relay, and this service starting up
        # against one of them should say so plainly and stop, not crash-loop.
        log.warning("No relay configured (ASTRA_MESHCENTRAL_URL unset). Nothing to do.")
        return 0

    # Fail loudly at startup rather than silently holding a connection that will never
    # authenticate. A listener that is up but unauthorised looks healthy and records
    # nothing, which is the worst of both.
    who = await client.ping()
    log.info("relay reachable at %s as %s", client.url, who.get("name"))

    await RemoteControlListener(SessionLocal, client).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
