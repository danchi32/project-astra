import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.devices import (
    DeviceRead,
    DeviceUpdate,
    EnrollmentTokenCreate,
    EnrollmentTokenCreated,
    EnrollmentTokenRead,
)
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
    devices = await DeviceService(session).list_devices(actor=actor)
    return [DeviceRead.from_device(d) for d in devices]


@router.get("/{device_id}", response_model=DeviceRead, summary="Get a device")
async def get_device(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceRead:
    device = await DeviceService(session).get_device(actor=actor, device_id=device_id)
    return DeviceRead.from_device(device)


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
