import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.report import AssetReport, FleetHealthReport, RemediationReport
from app.services.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_response(rows: list[dict[str, Any]], fieldnames: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/fleet-health", response_model=FleetHealthReport, summary="Fleet health report")
async def fleet_health_report(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FleetHealthReport:
    return await ReportService(session).fleet_health(actor=actor)


@router.get("/fleet-health/export", summary="Fleet health report (CSV)")
async def fleet_health_export(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    report = await ReportService(session).fleet_health(actor=actor)
    rows = [
        {
            "hostname": d.hostname,
            "status": d.status,
            "cpu_percent": d.cpu_percent,
            "ram_percent": d.ram_percent,
            "disk_free_percent_min": d.disk_free_percent_min,
            "critical_events": d.critical_event_count,
            "pending_updates": d.pending_update_count,
            "last_seen_at": d.last_seen_at,
        }
        for d in report.devices
    ]
    return _csv_response(
        rows,
        ["hostname", "status", "cpu_percent", "ram_percent", "disk_free_percent_min",
         "critical_events", "pending_updates", "last_seen_at"],
        "fleet-health-report.csv",
    )


@router.get("/remediation", response_model=RemediationReport, summary="Remediation activity report")
async def remediation_report(
    days: int = Query(default=30, ge=1, le=365),
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RemediationReport:
    return await ReportService(session).remediation_report(actor=actor, days=days)


@router.get("/remediation/export", summary="Remediation activity report (CSV)")
async def remediation_export(
    days: int = Query(default=30, ge=1, le=365),
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    report = await ReportService(session).remediation_report(actor=actor, days=days)
    rows = [
        {
            "device": t.device_hostname or "",
            "action": t.action_id,
            "tier": t.tier,
            "status": t.status,
            "source": t.source,
            "created_at": t.created_at,
            "completed_at": t.completed_at or "",
        }
        for t in report.tasks
    ]
    return _csv_response(
        rows,
        ["device", "action", "tier", "status", "source", "created_at", "completed_at"],
        "remediation-report.csv",
    )


@router.get("/assets", response_model=AssetReport, summary="Asset register report")
async def asset_report(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssetReport:
    return await ReportService(session).asset_report(actor=actor)


@router.get("/assets/export", summary="Asset register report (CSV)")
async def asset_export(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    report = await ReportService(session).asset_report(actor=actor)
    rows = [
        {
            "asset_tag": a.asset_tag or "",
            "name": a.name,
            "category": a.category.value,
            "status": a.status.value,
            "assigned_to": a.assigned_to_name or "",
            "device": a.device_hostname or "",
            "serial_number": a.serial_number or "",
            "cost": a.purchase_cost if a.purchase_cost is not None else "",
            "warranty_expiry": a.warranty_expiry or "",
        }
        for a in report.assets
    ]
    return _csv_response(
        rows,
        ["asset_tag", "name", "category", "status", "assigned_to", "device",
         "serial_number", "cost", "warranty_expiry"],
        "asset-report.csv",
    )
