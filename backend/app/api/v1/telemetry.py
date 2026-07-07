import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, get_current_user, require_roles
from app.core.database import get_db
from app.models import Device, User, UserRole
from app.schemas.telemetry import (
    DashboardSummary,
    DeviceEventLogRead,
    DeviceInstalledAppRead,
    DeviceServiceRead,
    DeviceWindowsUpdateRead,
    TelemetryPush,
    TelemetryPushResponse,
    TelemetrySnapshotRead,
)
from app.services.telemetry import TelemetryService

router = APIRouter(tags=["telemetry"])
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


# Agent pushes telemetry
@router.post(
    "/agent/telemetry",
    response_model=TelemetryPushResponse,
    summary="Submit a telemetry batch (agent only)",
)
async def push_telemetry(
    body: TelemetryPush,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> TelemetryPushResponse:
    await TelemetryService(session).ingest(device=device, data=body)
    return TelemetryPushResponse()


# Portal reads
@router.get(
    "/dashboard/summary",
    response_model=DashboardSummary,
    summary="Dashboard summary for the current org",
)
async def dashboard_summary(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    return await TelemetryService(session).get_dashboard_summary(actor=actor)


@router.get(
    "/devices/{device_id}/telemetry",
    response_model=list[TelemetrySnapshotRead],
    summary="Recent telemetry snapshots for a device",
)
async def get_snapshots(
    device_id: uuid.UUID,
    limit: int = Query(default=60, ge=1, le=1440),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[TelemetrySnapshotRead]:
    return await TelemetryService(session).get_snapshots(actor=actor, device_id=device_id, limit=limit)


@router.get(
    "/devices/{device_id}/events",
    response_model=list[DeviceEventLogRead],
    summary="Windows event log entries for a device",
)
async def get_event_logs(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceEventLogRead]:
    return await TelemetryService(session).get_event_logs(actor=actor, device_id=device_id)


@router.get(
    "/devices/{device_id}/apps",
    response_model=list[DeviceInstalledAppRead],
    summary="Installed applications on a device",
)
async def get_installed_apps(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceInstalledAppRead]:
    return await TelemetryService(session).get_installed_apps(actor=actor, device_id=device_id)


@router.get(
    "/devices/{device_id}/services",
    response_model=list[DeviceServiceRead],
    summary="Windows services on a device",
)
async def get_services(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceServiceRead]:
    return await TelemetryService(session).get_services(actor=actor, device_id=device_id)


@router.get(
    "/devices/{device_id}/updates",
    response_model=list[DeviceWindowsUpdateRead],
    summary="Windows updates on a device",
)
async def get_windows_updates(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceWindowsUpdateRead]:
    return await TelemetryService(session).get_windows_updates(actor=actor, device_id=device_id)
