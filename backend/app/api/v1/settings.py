from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.settings import (
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
    PermissionMatrix,
)
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

admin_required = require_roles(UserRole.ADMIN)


@router.get(
    "/organization",
    response_model=OrganizationSettingsRead,
    summary="Get organization settings (admin)",
)
async def get_org_settings(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> OrganizationSettingsRead:
    return await SettingsService(session).read(actor=actor)


@router.patch(
    "/organization",
    response_model=OrganizationSettingsRead,
    summary="Update organization settings (admin)",
)
async def update_org_settings(
    body: OrganizationSettingsUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> OrganizationSettingsRead:
    return await SettingsService(session).update(actor=actor, data=body)


@router.get(
    "/permissions",
    response_model=PermissionMatrix,
    summary="Role capability matrix for this organization",
)
async def get_permission_matrix(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PermissionMatrix:
    return await SettingsService(session).permission_matrix(org_id=actor.org_id)
