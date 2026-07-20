import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.location import LocationCreate, LocationRead, LocationUpdate
from app.services.exceptions import ConflictError
from app.services.locations import LocationService

router = APIRouter(prefix="/locations", tags=["locations"])

admin_required = require_roles(UserRole.ADMIN)


@router.get("", response_model=list[LocationRead], summary="List the org's locations")
async def list_locations(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[LocationRead]:
    return await LocationService(session).list_for_org(org_id=actor.org_id)


@router.post(
    "", response_model=LocationRead, status_code=status.HTTP_201_CREATED,
    summary="Add a location (admin)",
)
async def create_location(
    body: LocationCreate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> LocationRead:
    try:
        return await LocationService(session).create(actor=actor, name=body.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch(
    "/{location_id}", response_model=LocationRead, summary="Rename a location (admin)",
)
async def rename_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> LocationRead:
    try:
        return await LocationService(session).rename(
            actor=actor, location_id=location_id, name=body.name
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/{location_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a location (admin)",
)
async def delete_location(
    location_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await LocationService(session).delete(actor=actor, location_id=location_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))