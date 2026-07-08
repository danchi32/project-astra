"""Read-only evidence tools the cognitive engine can call.

Phase 4 is evidence-only — these tools observe device state so the AI can diagnose
(the Evidence-Before-Action principle). Action tools with approval gates arrive in
Phase 5 (self-healing).
"""
import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RemediationSource
from app.repositories.devices import DeviceRepository
from app.repositories.telemetry import TelemetryRepository
from app.schemas.devices import ONLINE_THRESHOLD
from app.models.base import as_utc, utcnow
from app.services.remediation.actions import ACTIONS
from app.services.remediation.service import RemediationError, RemediationService

_ACTION_IDS = sorted(ACTIONS.keys())

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
    {
        "name": "propose_remediation",
        "description": "Propose a fix for a problem on the user's own device. Call this only "
        "after you have gathered evidence and are confident of the cause. Automatic fixes "
        "(restarting an app, flushing DNS, clearing temp files) are applied immediately; "
        "higher-risk fixes are queued for the IT team to approve. Tell the user plainly what "
        "you did or that it's awaiting approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "enum": _ACTION_IDS,
                    "description": "The remediation action to apply.",
                },
                "service_name": {
                    "type": "string",
                    "description": "Only for restart_service: the Windows service to restart.",
                },
                "reason": {
                    "type": "string",
                    "description": "A short, plain-language reason for this fix.",
                },
            },
            "required": ["action_id", "reason"],
        },
    },
]


async def dispatch_tool(
    *,
    session: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    tool_input: dict[str, Any],
    acting_device_id: uuid.UUID | None = None,
) -> str:
    """Execute a tool call within the org's scope and return a JSON string result.

    `acting_device_id` is the device whose tray the chat came from; remediation acts on it.
    """
    devices = DeviceRepository(session)
    telemetry = TelemetryRepository(session)

    if name == "propose_remediation":
        return await _propose_remediation(
            session=session, org_id=org_id, acting_device_id=acting_device_id,
            tool_input=tool_input or {}
        )

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


async def _propose_remediation(
    *,
    session: AsyncSession,
    org_id: uuid.UUID,
    acting_device_id: uuid.UUID | None,
    tool_input: dict[str, Any],
) -> str:
    if acting_device_id is None:
        return json.dumps(
            {"error": "Remediation can only be applied from the device's own assistant."}
        )

    device = await DeviceRepository(session).get(acting_device_id)
    if device is None:
        return json.dumps({"error": "Device not found."})

    action_id = tool_input.get("action_id", "")
    reason = tool_input.get("reason", "Requested via the device assistant.")
    params: dict[str, Any] = {}
    if tool_input.get("service_name"):
        params["service_name"] = tool_input["service_name"]

    try:
        task = await RemediationService(session).create_task(
            org_id=org_id,
            device=device,
            action_id=action_id,
            params=params or None,
            reason=reason,
            source=RemediationSource.ASSISTANT,
            actor_user_id=None,
        )
    except RemediationError as exc:
        return json.dumps({"error": str(exc)})

    action = ACTIONS[action_id]
    if task.status.value == "approved":
        outcome = f"Applied automatically ({action.label}). The agent will run it shortly."
    else:
        outcome = f"Queued for IT approval ({action.label}); it needs a {task.tier} sign-off."
    return json.dumps({"task_id": str(task.id), "action": action.label, "outcome": outcome})
