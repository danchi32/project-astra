"""Entry point for the remote-control listener service.

This is a SERVICE, not a job. It serves no real HTTP traffic — it holds one connection to
the MeshCentral relay and writes what the relay reports into ASTRA's own record.

It DOES bind an HTTP port, and only because Cloud Run insists. Cloud Run probes the port
a container declares and refuses to route to a container that never answers, so a pure
socket-holder like this is marked unhealthy and the deploy fails. A trivial always-200
server on $PORT is the documented way to run a background worker on Cloud Run — it is a
liveness signal, nothing more, and the real work happens on the relay socket.

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
"""
import asyncio
import contextlib
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
# Settings reads `.env` relative to the working directory — see seed_builtin_assistant.py
# for the full story. Same fix, same reason.
os.chdir(BACKEND_DIR)

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.meshcentral import MeshCentralClient  # noqa: E402
from app.services.remote_control_listener import RemoteControlListener  # noqa: E402

log = logging.getLogger("astra.remote-listener")


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib method name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args):
        pass  # the probe hits this constantly; its logs are noise


def _serve_health() -> None:
    """Answer Cloud Run's probe on $PORT. Started first and on its own thread, so the
    container is healthy the instant it boots — before the relay is even contacted. A
    relay that is slow or briefly down must not read as a failed deploy."""
    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("0.0.0.0", port), _Health).serve_forever()


async def main() -> int:
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    threading.Thread(target=_serve_health, daemon=True).start()

    client = MeshCentralClient()
    if not client.configured:
        # Not an error. Most deployments have no relay, and this service should sit
        # quietly rather than crash-loop against Cloud Run's min-instances=1 restart.
        log.warning("No relay configured (ASTRA_MESHCENTRAL_URL unset). Idling.")
        await asyncio.Event().wait()   # stay up and healthy, do nothing
        return 0

    # Best-effort, and deliberately non-fatal. A relay that is briefly unreachable at boot
    # must not stop the service from starting — the run loop reconnects on its own, and
    # crashing here would just restart into the same wait.
    with contextlib.suppress(Exception):
        who = await client.ping()
        log.info("relay reachable at %s as %s", client.url, who.get("name"))

    await RemoteControlListener(SessionLocal, client).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
