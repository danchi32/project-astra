import uuid

from sqlalchemy import select
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

    async def add(self, device: Device) -> Device:
        self.session.add(device)
        await self.session.flush()
        return device

    async def delete(self, device: Device) -> None:
        await self.session.delete(device)
