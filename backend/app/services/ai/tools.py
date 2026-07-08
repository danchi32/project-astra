"""Read-only evidence tools the cognitive engine can call.

Phase 4 is evidence-only — these tools observe device state so the AI can diagnose
(the Evidence-Before-Action principle). Action tools with approval gates arrive in
Phase 5 (self-healing).
"""
import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.devices import DeviceRepository
from app.repositories.telemetry import TelemetryRepository
from app.schemas.devices import ONLINE_THRESHOLD
from app.models.base import as_utc, utcnow

# Anthropic tool schemas advertised to the model.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_devices",
        "description": "List all devices in the organization with their online/offline status. "
        "Use this first to discover which devices exist.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_device_telemetry",
        "description": "Get the latest CPU, RAM, and disk telemetry for one device, identified "
        "by its hostname. Use to diagnose performance or resource problems.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "The device hostname."}
            },
            "required": ["hostname"],
        },
    },
    {
        "name": "get_device_events",
        "description": "Get recent Windows event-log errors and warnings for one device, "
        "identified by its hostname. Use to find crash or service-failure evidence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "The device hostname."}
            },
            "required": ["hostname"],
        },
    },
]


async def dispatch_tool(
    *, session: AsyncSession, org_id: uuid.UUID, name: str, tool_input: dict[str, Any]
) -> str:
    """Execute a tool call within the org's scope and return a JSON string result."""
    devices = DeviceRepository(session)
    telemetry = TelemetryRepository(session)

    if name == "list_devices":
        rows = await devices.list_by_org(org_id)
        now = utcnow()
        return json.dumps(
            [
                {
                    "hostname": d.hostname,
                    "status": "online"
                    if d.last_seen_at is not None and now - as_utc(d.last_seen_at) < ONLINE_THRESHOLD
                    else "offline",
                    "os_version": d.os_version,
                }
                for d in rows
            ]
        )

    if name in ("get_device_telemetry", "get_device_events"):
        hostname = (tool_input or {}).get("hostname", "")
        device = await _find_by_hostname(devices, org_id, hostname)
        if device is None:
            return json.dumps({"error": f"No device found with hostname '{hostname}'."})

        if name == "get_device_telemetry":
            snap = await telemetry.get_latest_snapshot(device.id)
            if snap is None:
                return json.dumps({"error": "No telemetry reported yet for this device."})
            ram_pct = round(snap.ram_used_mb / snap.ram_total_mb * 100, 1) if snap.ram_total_mb else 0
            return json.dumps(
                {
                    "hostname": device.hostname,
                    "cpu_percent": snap.cpu_percent,
                    "ram_used_mb": snap.ram_used_mb,
                    "ram_total_mb": snap.ram_total_mb,
                    "ram_percent": ram_pct,
                    "disks": snap.disks,
                    "collected_at": snap.collected_at.isoformat(),
                }
            )

        events = await telemetry.get_event_logs(device.id, limit=20)
        return json.dumps(
            [
                {
                    "level": e.level,
                    "source": e.source,
                    "event_id": e.event_id,
                    "message": e.message[:300],
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in events
            ]
        )

    return json.dumps({"error": f"Unknown tool '{name}'."})


async def _find_by_hostname(repo: DeviceRepository, org_id: uuid.UUID, hostname: str):
    for device in await repo.list_by_org(org_id):
        if device.hostname.lower() == hostname.lower():
            return device
    return None
