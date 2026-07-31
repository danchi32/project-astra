import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build, clamp
from app.schemas.compliance import (
    BannedSoftwareCreate,
    BannedSoftwareRead,
    ComplianceSummary,
    DeviceCompliance,
)
from app.services.compliance import ComplianceService
from app.services.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/compliance", tags=["compliance"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)
admin_required = require_roles(UserRole.ADMIN)


@router.get("/summary", response_model=ComplianceSummary, summary="Fleet compliance posture")
async def compliance_summary(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> ComplianceSummary:
    return await ComplianceService(session).summary(org_id=actor.org_id)


@router.get("/devices", response_model=Page[DeviceCompliance], summary="Per-device compliance")
async def compliance_devices(
    needs_attention: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> Page[DeviceCompliance]:
    page, page_size = clamp(page, page_size)
    items, total = await ComplianceService(session).list_devices_page(
        org_id=actor.org_id, needs_attention=needs_attention,
        offset=(page - 1) * page_size, limit=page_size
    )
    return build(items, total, page, page_size)


@router.get(
    "/devices/{device_id}", response_model=DeviceCompliance, summary="One device's compliance",
)
async def compliance_device(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceCompliance:
    try:
        return await ComplianceService(session).get_device(org_id=actor.org_id, device_id=device_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/banned-software", response_model=list[BannedSoftwareRead], summary="The org's restricted-software list",
)
async def list_banned(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[BannedSoftwareRead]:
    return await ComplianceService(session).list_banned(org_id=actor.org_id)


@router.post(
    "/banned-software", response_model=BannedSoftwareRead,
    status_code=status.HTTP_201_CREATED, summary="Add restricted software (admin)",
)
async def add_banned(
    body: BannedSoftwareCreate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> BannedSoftwareRead:
    try:
        return await ComplianceService(session).add_banned(actor=actor, name=body.name)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/banned-software/{banned_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove restricted software (admin)",
)
async def remove_banned(
    banned_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await ComplianceService(session).remove_banned(actor=actor, banned_id=banned_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
