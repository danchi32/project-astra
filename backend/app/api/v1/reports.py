import csv
import io
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, requires
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.report import (
    AiSafetyReport,
    AssetReport,
    FleetHealthReport,
    RemediationReport,
    ValueReport,
)
from app.services.entitlements import AUDIT_EXPORT
from app.services.reports import ReportService

# Viewing reports is Essential; EXPORTING them is what Expert's "full audit trail &
# export" is sold as. Reading stays with everyone — for many customers the trail is
# their own compliance requirement, and removing it would make the cheap tier a
# liability rather than a smaller product.
router = APIRouter(
    prefix="/reports", tags=["reports"],
    dependencies=[Depends(requires(AUDIT_EXPORT))],
)


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


@router.get(
    "/ai-safety",
    response_model=AiSafetyReport,
    summary="AI Safety: assistant proposals, and those SAVIO held or refused (staff)",
)
async def ai_safety_report(
    days: int = Query(default=30, ge=1, le=365),
    # Staff only: it names devices and what was attempted on them. The people who approve
    # held fixes are the people who need to see why they were held.
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> AiSafetyReport:
    return await ReportService(session).ai_safety_report(actor=actor, days=days)


@router.get(
    "/value",
    response_model=ValueReport,
    summary="Value report: unattended fixes, hours and rupees saved, each with its basis (staff)",
)
async def value_report(
    days: int = Query(default=30, ge=1, le=365),
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> ValueReport:
    return await ReportService(session).value_report(actor=actor, days=days)


class BriefSection(BaseModel):
    key: str
    title: str
    lines: list[str]


class BriefRead(BaseModel):
    period: Literal["day", "week"]
    since: datetime
    generated_at: datetime
    title: str
    headline: str
    sections: list[BriefSection]
    footer: str


class BriefEmailRequest(BaseModel):
    period: Literal["day", "week"] = "day"


class BriefEmailed(BaseModel):
    sent: bool
    to: str


@router.get("/brief", response_model=BriefRead,
            summary="J1 brief: the day or week in plain business language (staff)")
async def get_brief(
    period: Literal["day", "week"] = Query(default="day"),
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> BriefRead:
    from app.services import brief

    return BriefRead(**await brief.build(session, actor=actor, period=period))


@router.post("/brief/email", response_model=BriefEmailed,
             summary="E-mail the J1 brief to yourself now (staff; audited; 5 an hour)")
async def email_brief(
    body: BriefEmailRequest,
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> BriefEmailed:
    from app.services import brief

    sent, to = await brief.send(session, actor=actor, period=body.period)
    return BriefEmailed(sent=sent, to=to)


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
