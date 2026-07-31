import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, device_id: uuid.UUID) -> Device | None:
        return await self.session.get(Device, device_id)

    async def get_by_token_hash(self, token_hash: str) -> Device | None:
        result = await self.session.execute(select(Device).where(Device.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def get_by_machine_id(self, org_id: uuid.UUID, machine_id: str) -> Device | None:
        result = await self.session.execute(
            select(Device).where(Device.org_id == org_id, Device.machine_id == machine_id)
        )
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: uuid.UUID) -> list[Device]:
        result = await self.session.execute(
            select(Device).where(Device.org_id == org_id).order_by(Device.hostname)
        )
        return list(result.scalars().all())

    async def hostnames_for(
        self, org_id: uuid.UUID, device_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """Hostnames for just the devices on the page being rendered. Labelling one page of
        tasks used to load the org's entire device table — 2,000 rows to name 50."""
        if not device_ids:
            return {}
        result = await self.session.execute(
            select(Device.id, Device.hostname).where(
                Device.org_id == org_id, Device.id.in_(device_ids)
            )
        )
        return {row[0]: row[1] for row in result.all()}

    async def list_page(
        self,
        org_id: uuid.UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        online_cutoff: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Device], int]:
        """A page of the org's devices, searched + optionally filtered by online status.
        Search and paging happen in the database so this scales to large fleets.
        Returns (page_items, total_matching)."""
        conditions = [Device.org_id == org_id]
        if q:
            like = f"%{q.lower()}%"
            conditions.append(
                or_(
                    func.lower(Device.hostname).like(like),
                    func.lower(Device.serial_number).like(like),
                    func.lower(Device.logged_in_user).like(like),
                    func.lower(Device.manufacturer).like(like),
                    func.lower(Device.model).like(like),
                    func.lower(Device.os_version).like(like),
                )
            )
        if status == "online" and online_cutoff is not None:
            conditions.append(Device.last_seen_at.is_not(None))
            conditions.append(Device.last_seen_at >= online_cutoff)
        elif status == "offline" and online_cutoff is not None:
            conditions.append(
                or_(Device.last_seen_at.is_(None), Device.last_seen_at < online_cutoff)
            )
        where = and_(*conditions)

        total = (
            await self.session.execute(select(func.count()).select_from(Device).where(where))
        ).scalar_one()
        result = await self.session.execute(
            select(Device).where(where).order_by(Device.hostname).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), int(total)

    async def add(self, device: Device) -> Device:
        self.session.add(device)
        await self.session.flush()
        return device

    async def delete(self, device: Device) -> None:
        await self.session.delete(device)
