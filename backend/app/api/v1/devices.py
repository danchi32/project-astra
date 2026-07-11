import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.devices import (
    AgentInstallerRequest,
    AgentInstallerResponse,
    DeviceRead,
    DeviceUpdate,
    EnrollmentTokenCreate,
    EnrollmentTokenCreated,
    EnrollmentTokenRead,
)
from app.schemas.telemetry import (
    DeviceEventLogRead,
    DeviceInstalledAppRead,
    DeviceServiceRead,
    DeviceWindowsUpdateRead,
    TelemetrySnapshotRead,
)
from app.repositories.telemetry import TelemetryRepository
from app.services.devices import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)
admin_required = require_roles(UserRole.ADMIN)


# Enrollment-token routes are declared before /{device_id} so the literal path wins.
@router.post(
    "/enrollment-tokens",
    response_model=EnrollmentTokenCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create an enrollment token (admin only) — the token is shown only once",
)
async def create_enrollment_token(
    body: EnrollmentTokenCreate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> EnrollmentTokenCreated:
    record, raw = await DeviceService(session).create_enrollment_token(actor=actor, data=body)
    return EnrollmentTokenCreated(
        id=record.id, name=record.name, token=raw, expires_at=record.expires_at
    )


@router.post(
    "/agent-installer",
    response_model=AgentInstallerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a pre-configured Windows agent installer (admin only)",
)
async def generate_agent_installer(
    body: AgentInstallerRequest,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> AgentInstallerResponse:
    return await DeviceService(session).generate_agent_installer(actor=actor, data=body)


@router.post(
    "/offline-installer",
    summary="Generate an offline mass-deployment installer bundle (.zip, admin only)",
    responses={201: {"content": {"application/zip": {}}}},
    status_code=status.HTTP_201_CREATED,
)
async def generate_offline_installer(
    body: AgentInstallerRequest,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> Response:
    filename, content = await DeviceService(session).generate_offline_bundle(
        actor=actor, data=body
    )
    return Response(
        content=content,
        status_code=status.HTTP_201_CREATED,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/enrollment-tokens",
    response_model=list[EnrollmentTokenRead],
    summary="List enrollment tokens (admin only)",
)
async def list_enrollment_tokens(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
):
    return await DeviceService(session).list_enrollment_tokens(actor=actor)


@router.delete(
    "/enrollment-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an enrollment token (admin only)",
)
async def revoke_enrollment_token(
    token_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    await DeviceService(session).revoke_enrollment_token(actor=actor, token_id=token_id)


@router.get("", response_model=list[DeviceRead], summary="List devices in your organization")
async def list_devices(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceRead]:
    service = DeviceService(session)
    devices = await service.list_devices(actor=actor)
    counts = await TelemetryRepository(session).count_apps_by_device_for_org(actor.org_id)
    return [DeviceRead.from_device(d, counts.get(d.id, 0)) for d in devices]


@router.get("/{device_id}", response_model=DeviceRead, summary="Get a device")
async def get_device(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceRead:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    count = await TelemetryRepository(session).count_apps_for_device(device.id)
    return DeviceRead.from_device(device, count)


@router.patch("/{device_id}", response_model=DeviceRead, summary="Update a device (admin only)")
async def update_device(
    device_id: uuid.UUID,
    body: DeviceUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceRead:
    device = await DeviceService(session).update_device(
        actor=actor, device_id=device_id, data=body
    )
    return DeviceRead.from_device(device)


@router.delete(
    "/{device_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a device (admin only)"
)
async def delete_device(
    device_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    await DeviceService(session).delete_device(actor=actor, device_id=device_id)


# ── Per-device detail (telemetry history + inventory) ───────────────────────
# Each first resolves the device via DeviceService.get_device, which raises 404
# if the device is not in the actor's organization — keeping these org-scoped.


@router.get(
    "/{device_id}/telemetry",
    response_model=list[TelemetrySnapshotRead],
    summary="Recent telemetry snapshots for a device",
)
async def get_device_telemetry(
    device_id: uuid.UUID,
    limit: int = 60,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[TelemetrySnapshotRead]:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    rows = await TelemetryRepository(session).get_snapshots(device.id, limit=limit)
    return [TelemetrySnapshotRead.model_validate(r) for r in rows]


@router.get(
    "/{device_id}/events",
    response_model=list[DeviceEventLogRead],
    summary="Recent Windows event-log entries for a device",
)
async def get_device_events(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceEventLogRead]:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    rows = await TelemetryRepository(session).get_event_logs(device.id)
    return [DeviceEventLogRead.model_validate(r) for r in rows]


@router.get(
    "/{device_id}/apps",
    response_model=list[DeviceInstalledAppRead],
    summary="Installed applications for a device",
)
async def get_device_apps(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceInstalledAppRead]:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    rows = await TelemetryRepository(session).get_installed_apps(device.id)
    return [DeviceInstalledAppRead.model_validate(r) for r in rows]


@router.get(
    "/{device_id}/services",
    response_model=list[DeviceServiceRead],
    summary="Windows services for a device",
)
async def get_device_services(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceServiceRead]:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    rows = await TelemetryRepository(session).get_services(device.id)
    return [DeviceServiceRead.model_validate(r) for r in rows]


@router.get(
    "/{device_id}/updates",
    response_model=list[DeviceWindowsUpdateRead],
    summary="Windows updates for a device",
)
async def get_device_updates(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceWindowsUpdateRead]:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    rows = await TelemetryRepository(session).get_windows_updates(device.id)
    return [DeviceWindowsUpdateRead.model_validate(r) for r in rows]
