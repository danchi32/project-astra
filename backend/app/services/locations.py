import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Location, User
from app.schemas.location import LocationRead
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError


class LocationService:
    """Manages an organization's location list. Assets store the location NAME, so a rename
    cascades to its assets and a delete is blocked while assets still reference it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def _asset_counts(self, org_id: uuid.UUID) -> dict[str, int]:
        rows = (await self.session.execute(
            select(Asset.location, func.count())
            .where(Asset.org_id == org_id, Asset.location.is_not(None))
            .group_by(Asset.location)
        )).all()
        return {name: n for name, n in rows if name}

    async def list_for_org(self, *, org_id: uuid.UUID) -> list[LocationRead]:
        locations = (await self.session.execute(
            select(Location).where(Location.org_id == org_id).order_by(Location.name)
        )).scalars().all()
        counts = await self._asset_counts(org_id)
        return [
            LocationRead(id=loc.id, name=loc.name, asset_count=counts.get(loc.name, 0))
            for loc in locations
        ]

    async def _get_owned(self, org_id: uuid.UUID, location_id: uuid.UUID) -> Location:
        loc = (await self.session.execute(
            select(Location).where(Location.id == location_id, Location.org_id == org_id)
        )).scalar_one_or_none()
        if loc is None:
            raise NotFoundError("Location not found")
        return loc

    async def _name_taken(self, org_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None) -> bool:
        q = select(Location).where(
            Location.org_id == org_id, func.lower(Location.name) == name.lower()
        )
        loc = (await self.session.execute(q)).scalars().first()
        return loc is not None and loc.id != exclude_id

    async def create(self, *, actor: User, name: str) -> LocationRead:
        name = name.strip()
        if not name:
            raise ValueError("Location name is required.")
        if await self._name_taken(actor.org_id, name):
            raise ConflictError("A location with that name already exists.")
        loc = Location(org_id=actor.org_id, name=name)
        self.session.add(loc)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="location.create",
            target_type="location", target_id=name,
        )
        await self.session.commit()
        await self.session.refresh(loc)
        return LocationRead(id=loc.id, name=loc.name, asset_count=0)

    async def rename(self, *, actor: User, location_id: uuid.UUID, name: str) -> LocationRead:
        name = name.strip()
        if not name:
            raise ValueError("Location name is required.")
        loc = await self._get_owned(actor.org_id, location_id)
        old = loc.name
        if name.lower() != old.lower() and await self._name_taken(actor.org_id, name, exclude_id=loc.id):
            raise ConflictError("A location with that name already exists.")
        loc.name = name
        # Cascade the rename to every asset carrying the old name.
        await self.session.execute(
            update(Asset).where(Asset.org_id == actor.org_id, Asset.location == old).values(location=name)
        )
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="location.rename",
            target_type="location", target_id=str(loc.id), detail={"from": old, "to": name},
        )
        await self.session.commit()
        counts = await self._asset_counts(actor.org_id)
        return LocationRead(id=loc.id, name=loc.name, asset_count=counts.get(loc.name, 0))

    async def delete(self, *, actor: User, location_id: uuid.UUID) -> None:
        loc = await self._get_owned(actor.org_id, location_id)
        in_use = (await self.session.execute(
            select(func.count()).select_from(Asset).where(
                Asset.org_id == actor.org_id, Asset.location == loc.name
            )
        )).scalar_one()
        if in_use:
            raise ConflictError(
                f"{in_use} asset{'s' if in_use != 1 else ''} are still in this location — "
                "reassign them first."
            )
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="location.delete",
            target_type="location", target_id=loc.name,
        )
        await self.session.delete(loc)
        await self.session.commit()
