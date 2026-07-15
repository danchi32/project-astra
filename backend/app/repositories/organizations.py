import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, org_id: uuid.UUID) -> Organization | None:
        return await self.session.get(Organization, org_id)

    async def get_by_name(self, name: str) -> Organization | None:
        result = await self.session.execute(
            select(Organization).where(Organization.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_enrollment_key(self, key: str) -> Organization | None:
        result = await self.session.execute(
            select(Organization).where(Organization.agent_enrollment_key == key)
        )
        return result.scalar_one_or_none()

    async def add(self, org: Organization) -> Organization:
        self.session.add(org)
        await self.session.flush()
        return org
