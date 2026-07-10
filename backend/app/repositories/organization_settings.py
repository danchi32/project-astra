import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrganizationSettings


class OrganizationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_org(self, org_id: uuid.UUID) -> OrganizationSettings | None:
        result = await self.session.execute(
            select(OrganizationSettings).where(OrganizationSettings.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def add(self, settings: OrganizationSettings) -> OrganizationSettings:
        self.session.add(settings)
        await self.session.flush()
        return settings
