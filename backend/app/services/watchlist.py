"""N2 · Watchlist: the things that go wrong by NOT happening.

N1 alerts fire as telemetry arrives, so they cannot see a PC that has stopped sending, a
warranty date passing, or a fix that never finishes: each is noticed only by the absence of
an event. Those need a clock. Per the 2.0 decision (16 Nov) there is no scheduler yet, so this
is the same list on demand: open the page and see it. When a scheduler arrives, it calls
`build` and turns new entries into notifications through the N1 `AlertState` table.

Four lists, each read straight from the database:
- PCs silent for more than N hours (last seen, or enrolled and never seen);
- warranties ending within 90 days, or ended in the last 30;
- work stuck for over a day (queued or running, never finished), grouped by rollout;
- PCs behind the current signed agent release, when an update channel is configured.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Asset, Device, RemediationStatus, RemediationTask
from app.models.base import as_utc, utcnow
from app.models.deployment import Deployment
from app.services.agent_update import AgentUpdateService
from app.services.remediation.actions import get_action

WARRANTY_DAYS = 90
STUCK_AFTER = timedelta(hours=24)


def _version(v: str | None) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in (v or "").split(".")[:3])
    except ValueError:
        return ()


async def latest_agent_version() -> str | None:
    current = await AgentUpdateService(get_settings()).current()
    if current is None:
        return None
    try:
        return str(json.loads(current[0]).get("version") or "") or None
    except (ValueError, AttributeError):
        return None


async def build(session: AsyncSession, *, org_id: uuid.UUID, silent_hours: int) -> dict:
    # First, before any query: on a cold cache this is an outbound fetch, and it must not
    # hold a database connection open while it waits.
    latest = await latest_agent_version()
    now = utcnow()
    devices = (await session.execute(
        select(Device).where(Device.org_id == org_id, Device.is_active.is_(True)))).scalars().all()

    silent = []
    for d in devices:
        since = as_utc(d.last_seen_at or d.created_at)
        hours = int((now - since).total_seconds() // 3600)
        if hours >= silent_hours:
            silent.append({"device_id": d.id, "hostname": d.hostname, "last_seen_at": d.last_seen_at,
                           "hours": hours})
    silent.sort(key=lambda r: -r["hours"])

    today = date.today()
    warranty = []
    for a in (await session.execute(select(Asset).where(
            Asset.org_id == org_id, Asset.archived_at.is_(None), Asset.warranty_expiry.is_not(None),
            Asset.warranty_expiry >= (today - timedelta(days=30)).isoformat(),
            Asset.warranty_expiry <= (today + timedelta(days=WARRANTY_DAYS)).isoformat(),
    ).order_by(Asset.warranty_expiry))).scalars():
        try:
            left = (date.fromisoformat(a.warranty_expiry) - today).days
        except ValueError:
            continue    # a malformed legacy date ("2026-12-1") must not take the whole list down
        bucket = "expired" if left < 0 else "30" if left <= 30 else "60" if left <= 60 else "90"
        warranty.append({"asset_id": a.id, "name": a.name, "ends": a.warranty_expiry,
                         "days_left": left, "bucket": bucket})

    hosts = {d.id: d.hostname for d in devices}
    stuck_rows = (await session.execute(
        select(RemediationTask, Deployment.title)
        .outerjoin(Deployment, Deployment.id == RemediationTask.deployment_id)
        .where(RemediationTask.org_id == org_id,
               RemediationTask.status.in_((RemediationStatus.APPROVED, RemediationStatus.DISPATCHED)),
               RemediationTask.created_at <= now - STUCK_AFTER)
        .order_by(RemediationTask.created_at)
    )).all()
    stuck = []
    for t, title in stuck_rows:
        action = get_action(t.action_id)
        stuck.append({
            "task_id": t.id, "action": action.label if action else t.action_id,
            "hostname": hosts.get(t.device_id), "rollout": title,
            # Queued means the PC never collected it (likely off); running means it collected
            # it and never reported back.
            "state": "never collected" if t.status is RemediationStatus.APPROVED else "never finished",
            "hours": int((now - as_utc(t.created_at)).total_seconds() // 3600),
        })

    behind = []
    if latest:
        behind = sorted(({"hostname": d.hostname, "version": d.agent_version} for d in devices
                         if d.agent_version and _version(d.agent_version) < _version(latest)),
                        key=lambda r: r["hostname"])
    return {"silent_hours": silent_hours, "silent": silent, "warranty": warranty, "stuck": stuck,
            "latest_agent": latest, "agents_behind": behind}
