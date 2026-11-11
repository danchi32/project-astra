"""L3 — "Ask SAVIO": read-only evidence tools over inventory, updates, compliance and assets.

Two kinds, and who gets which is the whole design:

* **Device tools** (``get_installed_apps``, ``get_windows_updates``, ``get_device_compliance``)
  take a hostname. In the employee's tray chat they only ever answer for THAT person's own
  machine — an employee asking about a colleague's laptop gets a refusal, not the data.
* **Fleet tools** (``fleet_summary``, ``find_assets``) answer across the organisation, so they
  are advertised only to portal staff (admin / technician). An end user never sees them, and a
  model that cannot see a tool cannot be talked into calling it.

Workforce ("Tracker") data is deliberately absent: it is employee monitoring, and a chat box
is the wrong place for it to leak out of. Everything here is read-only; tool outputs are data
returned in the tool-result channel, never instructions.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Device, User
from app.repositories.telemetry import TelemetryRepository
from app.services.compliance import ComplianceService

_HOST = {"hostname": {"type": "string", "description": "The device hostname."}}

DEVICE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_installed_apps",
        "description": "List the software installed on one device (name, version, publisher, "
        "and whether it is installed machine-wide or for one user only). Use to answer "
        "'is X installed', find unwanted or AI tools, or check a version.",
        "input_schema": {"type": "object", "properties": {
            **_HOST,
            "contains": {"type": "string",
                         "description": "Optional: only apps whose name contains this text."},
        }, "required": ["hostname"]},
    },
    {
        "name": "get_windows_updates",
        "description": "List Windows updates on one device that are pending, failed, or "
        "waiting for a restart. Use for patching questions.",
        "input_schema": {"type": "object", "properties": _HOST, "required": ["hostname"]},
    },
    {
        "name": "get_device_compliance",
        "description": "Get one device's security and compliance checks: updates, disk space, "
        "Defender, firewall, critical errors, restricted software, Windows activation and "
        "cracked activation. Each check is pass / fail / unknown with a detail.",
        "input_schema": {"type": "object", "properties": _HOST, "required": ["hostname"]},
    },
]

FLEET_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "fleet_summary",
        "description": "Across every device in the organization: how many pass/fail each "
        "compliance check, with the hostnames failing it. Use for questions like 'which PCs "
        "have Defender off', 'how many machines aren't activated', 'what is our biggest risk'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "find_assets",
        "description": "Search the asset register: name, tag, serial, model, assignee, "
        "status, purchase date and warranty. Use for 'whose warranty ends this month', "
        "'which laptop does Priya have', 'what is in storage'.",
        "input_schema": {"type": "object", "properties": {
            "text": {"type": "string", "description": "Optional free text: name, tag, serial, "
                     "model or the assignee's name."},
            "warranty_expiring_within_days": {"type": "integer", "minimum": 0, "maximum": 730,
                                              "description": "Optional: only assets whose "
                                              "warranty ends within this many days."},
        }},
    },
]

DEVICE_TOOLS = frozenset(t["name"] for t in DEVICE_TOOL_SCHEMAS)
FLEET_TOOLS = frozenset(t["name"] for t in FLEET_TOOL_SCHEMAS)

_MAX_ROWS = 60


def _err(msg: str) -> str:
    return json.dumps({"error": msg})


async def _device(session, org_id, hostname: str) -> Device | None:
    return (await session.execute(
        select(Device).where(Device.org_id == org_id,
                             Device.hostname.ilike((hostname or "").strip()))
    )).scalars().first()


async def dispatch(
    *,
    session: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    tool_input: dict[str, Any],
    acting_device_id: uuid.UUID | None,
    fleet_access: bool,
) -> str | None:
    """Run one of this module's tools, or return None if `name` isn't one of them."""
    tool_input = tool_input or {}

    if name in FLEET_TOOLS:
        # Belt and braces: the schema is withheld from non-staff, and the call is refused too.
        if not fleet_access:
            return _err("That information is only available to IT staff in the portal.")
        if name == "fleet_summary":
            return await _fleet_summary(session, org_id)
        return await _find_assets(session, org_id, tool_input)

    if name not in DEVICE_TOOLS:
        return None

    device = await _device(session, org_id, tool_input.get("hostname", ""))
    if device is None:
        return _err(f"No device found with hostname '{tool_input.get('hostname', '')}'.")
    if not fleet_access and device.id != acting_device_id:
        return _err("You can only look up your own device here.")

    telemetry = TelemetryRepository(session)
    if name == "get_installed_apps":
        needle = (tool_input.get("contains") or "").strip().lower()
        apps = [a for a in await telemetry.get_installed_apps(device.id)
                if not needle or needle in a.name.lower()]
        return json.dumps({"hostname": device.hostname, "count": len(apps), "apps": [
            {"name": a.name, "version": a.version, "publisher": a.publisher, "scope": a.scope,
             **({"user": a.user_name} if a.scope == "user" else {})}
            for a in apps[:_MAX_ROWS]
        ], **({"truncated": True} if len(apps) > _MAX_ROWS else {})})

    if name == "get_windows_updates":
        rows = [u for u in await telemetry.get_windows_updates(device.id) if u.state != "installed"]
        return json.dumps({"hostname": device.hostname, "outstanding": [
            {"kb": u.kb_article_id, "title": u.title, "state": u.state,
             **({"error_code": u.error_code} if u.error_code else {})}
            for u in rows[:_MAX_ROWS]
        ]})

    comp = await ComplianceService(session).get_device(org_id=org_id, device_id=device.id)
    return json.dumps({"hostname": device.hostname, "status": comp.status, "score": comp.score,
                       "checks": [{"check": c.label, "status": c.status, "detail": c.detail}
                                  for c in comp.checks]})


async def _fleet_summary(session: AsyncSession, org_id: uuid.UUID) -> str:
    rows = await ComplianceService(session).evaluate_all(org_id=org_id)
    by_check: dict[str, dict[str, Any]] = {}
    for dev in rows:
        for c in dev.checks:
            entry = by_check.setdefault(c.label, {"pass": 0, "fail": 0, "unknown": 0, "failing": []})
            entry[c.status] += 1
            if c.status == "fail" and len(entry["failing"]) < 15:
                entry["failing"].append(f"{dev.hostname}: {c.detail}")
    return json.dumps({"devices": len(rows), "checks": by_check})


async def _find_assets(session: AsyncSession, org_id: uuid.UUID, tool_input: dict[str, Any]) -> str:
    stmt = (select(Asset, User.full_name, Device.hostname)
            .outerjoin(User, User.id == Asset.assigned_to_user_id)
            .outerjoin(Device, Device.id == Asset.device_id)
            .where(Asset.org_id == org_id, Asset.archived_at.is_(None)))
    text = (tool_input.get("text") or "").strip()
    if text:
        like = f"%{text}%"
        stmt = stmt.where(or_(Asset.name.ilike(like), Asset.asset_tag.ilike(like),
                              Asset.serial_number.ilike(like), Asset.model.ilike(like),
                              User.full_name.ilike(like), Device.hostname.ilike(like)))
    days = tool_input.get("warranty_expiring_within_days")
    if isinstance(days, int):
        # Stored as yyyy-mm-dd text, so string comparison orders correctly.
        today = date.today()
        stmt = stmt.where(Asset.warranty_expiry.is_not(None),
                          Asset.warranty_expiry >= today.isoformat(),
                          Asset.warranty_expiry <= (today + timedelta(days=days)).isoformat())
    rows = (await session.execute(stmt.order_by(Asset.name).limit(_MAX_ROWS + 1))).all()
    return json.dumps({"assets": [
        {"name": a.name, "tag": a.asset_tag, "category": a.category.value, "status": a.status.value,
         "assigned_to": who, "device": host, "manufacturer": a.manufacturer, "model": a.model,
         "serial": a.serial_number, "purchase_date": a.purchase_date,
         "warranty_expiry": a.warranty_expiry}
        for a, who, host in rows[:_MAX_ROWS]
    ], **({"truncated": True} if len(rows) > _MAX_ROWS else {})})
