import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.asset import AssetCreate, AssetRead, AssetSummary, AssetUpdate
from app.services.assets import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("", response_model=list[AssetRead], summary="List assets in your organization")
async def list_assets(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AssetRead]:
    return await AssetService(session).list_for_org(org_id=actor.org_id)


@router.get("/summary", response_model=AssetSummary, summary="Asset register summary")
async def asset_summary(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssetSummary:
    return await AssetService(session).summary(org_id=actor.org_id)


@router.get("/{asset_id}", response_model=AssetRead, summary="Get an asset")
async def get_asset(
    asset_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).get(actor=actor, asset_id=asset_id)


@router.post(
    "", response_model=AssetRead, status_code=status.HTTP_201_CREATED,
    summary="Create an asset (staff)",
)
async def create_asset(
    body: AssetCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).create(actor=actor, data=body)


@router.patch("/{asset_id}", response_model=AssetRead, summary="Update an asset (staff)")
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).update(actor=actor, asset_id=asset_id, data=body)


@router.delete(
    "/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an asset (staff)"
)
async def delete_asset(
    asset_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    await AssetService(session).delete(actor=actor, asset_id=asset_id)
