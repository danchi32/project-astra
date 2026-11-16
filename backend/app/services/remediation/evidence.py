"""C1 · Proof-of-Fix: the measurement a fix was meant to move, before and after.

"The agent said it worked" is the agent's claim. The proof is the number the fix was for,
read the same way before it ran and again afterwards: free space on C: for a clean-up, the
three firewall profiles for "turn on the firewall", and so on.

- **before** is read when the task is handed to the agent (dispatch), from the latest data.
- **after** is read from the first push the agent sends after reporting success that carries
  that kind of data. A push without it (inventory is hourly) leaves the task waiting.
- **recheck**: the first such push at least 7 days after the fix. Did the problem come back?

All of it happens on the agent's own pushes, so nothing here needs a scheduler. A PC that
stays offline is simply not rechecked yet, which is the truth.

Actions with nothing to measure (restart Outlook, flush DNS) carry no evidence. The task page
then says "no measurement for this fix" rather than inventing one.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RemediationStatus, RemediationTask
from app.models.base import as_utc, utcnow
from app.models.telemetry import UPDATE_INSTALLED, DevicePosture
from app.repositories.telemetry import TelemetryRepository

RECHECK_AFTER = timedelta(days=7)
# Stop looking for an "after" or a recheck once a task is this old.
GIVE_UP_AFTER = timedelta(days=30)


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    better: str      # "up" | "down" | "true"
    source: str      # which part of a push carries it: snapshot | posture | updates | services


SYSTEM_DISK_FREE = Metric("system_disk_free_gb", "Free space on the system drive", "GB", "up", "snapshot")
FIREWALL_ON = Metric("firewall_on", "Firewall on for every profile", "", "true", "posture")
DEFENDER_ON = Metric("defender_realtime", "Defender real-time protection", "", "true", "posture")
UPDATES_OUTSTANDING = Metric("updates_outstanding", "Windows updates outstanding", "", "down", "updates")
SERVICE_RUNNING = Metric("service_running", "Service running", "", "true", "services")

METRICS: dict[str, Metric] = {
    "clear_temp": SYSTEM_DISK_FREE,
    "clear_system_temp": SYSTEM_DISK_FREE,
    "clear_browser_cache": SYSTEM_DISK_FREE,
    "enable_firewall": FIREWALL_ON,
    "enable_defender_realtime": DEFENDER_ON,
    "windows_update_install": UPDATES_OUTSTANDING,
    "restart_service": SERVICE_RUNNING,
}

# Free space moves a little on its own; smaller changes are "unchanged".
_DISK_NOISE_GB = 0.1


async def read(session: AsyncSession, device_id, metric: Metric, params: dict[str, Any] | None):
    """The metric's current value for a device, or None when the device hasn't reported it."""
    repo = TelemetryRepository(session)
    if metric is SYSTEM_DISK_FREE:
        snap = await repo.get_latest_snapshot(device_id)
        disks = (snap.disks or []) if snap else []
        disk = next((d for d in disks if str(d.get("drive", "")).upper().startswith("C")),
                    disks[0] if disks else None)
        return round(float(disk["free_gb"]), 1) if disk and disk.get("free_gb") is not None else None
    if metric.source == "posture":
        p = await session.scalar(select(DevicePosture).where(DevicePosture.device_id == device_id))
        if p is None:
            return None
        if metric is DEFENDER_ON:
            return p.defender_realtime
        profiles = (p.firewall_domain, p.firewall_private, p.firewall_public)
        if False in profiles:
            return False
        return True if None not in profiles else None
    if metric is UPDATES_OUTSTANDING:
        return sum(1 for u in await repo.get_windows_updates(device_id) if u.state != UPDATE_INSTALLED)
    if metric is SERVICE_RUNNING:
        name = str((params or {}).get("service_name", "")).lower()
        svc = next((s for s in await repo.get_services(device_id) if s.name.lower() == name), None)
        return None if svc is None else str(svc.status).lower() == "running"
    return None


def verdict(metric: Metric, before, after) -> str:
    """improved | unchanged | worse | unmeasured."""
    if before is None or after is None:
        return "unmeasured"
    if metric.better == "true":
        if after is True:
            return "unchanged" if before is True else "improved"
        return "worse" if before is True else "unchanged"
    delta = after - before if metric.better == "up" else before - after
    noise = _DISK_NOISE_GB if metric is SYSTEM_DISK_FREE else 0
    if delta > noise:
        return "improved"
    return "worse" if delta < -noise else "unchanged"


def held(metric: Metric, before, value) -> bool | None:
    """At the 7-day recheck: is it still no worse than before the fix?"""
    if before is None or value is None:
        return None
    if metric.better == "true":
        return value is True
    return value >= before - _DISK_NOISE_GB if metric.better == "up" else value <= before


async def capture_before(session: AsyncSession, task: RemediationTask) -> None:
    metric = METRICS.get(task.action_id)
    if metric is None:
        return
    task.evidence = {
        "metric": metric.key, "label": metric.label, "unit": metric.unit,
        "before": await read(session, task.device_id, metric, task.params),
        "before_at": utcnow().isoformat(),
    }


async def observe(session: AsyncSession, *, device_id, collected_at, sources: set[str]) -> None:
    """Called on every telemetry push: fill in any "after" or recheck this push can answer.

    `sources` names what the push carried, so a reading is only ever taken from data the
    agent sent after the fix, never from an older row still sitting in the table.
    """
    now = utcnow()
    tasks = (await session.execute(
        select(RemediationTask).where(
            RemediationTask.device_id == device_id,
            RemediationTask.status == RemediationStatus.SUCCEEDED,
            RemediationTask.evidence.is_not(None),
            RemediationTask.completed_at >= now - GIVE_UP_AFTER,
        ).order_by(RemediationTask.completed_at).limit(50)
    )).scalars().all()
    for task in tasks:
        ev = dict(task.evidence or {})
        metric = METRICS.get(task.action_id)
        if metric is None or metric.source not in sources or "recheck" in ev:
            continue
        if as_utc(collected_at) <= as_utc(task.completed_at):
            continue
        # Decide what this push is for before reading anything: a task between its "after"
        # and its 7-day recheck needs nothing, and must not cost a query on every push.
        if "after" not in ev:
            step = "after"
        elif now - as_utc(task.completed_at) >= RECHECK_AFTER:
            step = "recheck"
        else:
            continue
        value = await read(session, device_id, metric, task.params)
        if step == "after":
            ev.update(after=value, after_at=now.isoformat(),
                      verdict=verdict(metric, ev.get("before"), value))
        else:
            ev["recheck"] = {"at": now.isoformat(), "value": value,
                             "held": held(metric, ev.get("before"), value)}
        task.evidence = ev  # a new dict, so the JSON column is seen as changed
