"""Bump the demo fleet's last check-in to now.

A device counts as online for three minutes after its heartbeat, so seeded data
starts reading as "not checking in" a few minutes after seed_presentation.py runs.
Run this immediately before capturing screenshots or presenting a live demo.

The two devices that are deliberately silent (TM-SAL-0407, TM-WH-0702) keep their
age — the demo needs something for the "not checking in" alert to point at. A real
machine enrolled into the demo org is never touched: its status is its own agent's.

    backend/.venv/Scripts/python.exe backend/scripts/refresh_demo_heartbeat.py

For a live demo, keep the fleet online for the length of the session instead:

    ... refresh_demo_heartbeat.py --minutes 90

Production: the same Cloud Run Job shape as seed_presentation.py (database, JWT secret),
with `--args scripts/refresh_demo_heartbeat.py,--minutes,90` and a task timeout longer
than the demo.
"""
import argparse
import asyncio
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

if "ASTRA_DATABASE_URL" not in os.environ:
    DB_PATH = os.path.join(BACKEND_DIR, "astra-demo.db").replace("\\", "/")
    os.environ["ASTRA_DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"
    os.environ.setdefault("ASTRA_JWT_SECRET_KEY", "demo-secret-key-local-only-not-for-prod")

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Device, Organization, TelemetrySnapshot  # noqa: E402

ORG_NAME = "Technomate IT Solution"
DELIBERATELY_OFFLINE = {"TM-SAL-0407", "TM-WH-0702"}
# Well inside the three-minute online window, so no device flickers between passes.
INTERVAL_SECONDS = 60


def is_seeded(device: Device) -> bool:
    """seed_presentation.py derives machine_id from the hostname; a real agent never does."""
    return device.machine_id == hashlib.sha256(device.hostname.encode()).hexdigest()[:32]


async def refresh() -> int:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as s:
        org = (await s.execute(
            select(Organization).where(Organization.name == ORG_NAME, Organization.is_demo.is_(True))
        )).scalar_one_or_none()
        if org is None:
            sys.exit(f"Demo org '{ORG_NAME}' not found — run seed_presentation.py first.")

        devices = (await s.execute(select(Device).where(Device.org_id == org.id))).scalars().all()
        bumped = 0
        for d in devices:
            if d.hostname in DELIBERATELY_OFFLINE or not is_seeded(d):
                continue
            d.last_seen_at = now
            bumped += 1

            # Move the newest telemetry sample forward too, so the device page's
            # "collected" timestamp agrees with the heartbeat.
            latest = (await s.execute(
                select(TelemetrySnapshot)
                .where(TelemetrySnapshot.device_id == d.id)
                .order_by(TelemetrySnapshot.collected_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if latest is not None:
                latest.collected_at = now - timedelta(seconds=20)

        await s.commit()
    return bumped


async def main(minutes: float) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    while True:
        bumped = await refresh()
        print(f"Refreshed {bumped} devices to now ({len(DELIBERATELY_OFFLINE)} left offline on purpose).",
              flush=True)
        if datetime.now(timezone.utc) + timedelta(seconds=INTERVAL_SECONDS) > deadline:
            return
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=float, default=0,
                        help="keep refreshing every minute for this long (default: once)")
    asyncio.run(main(parser.parse_args().minutes))
