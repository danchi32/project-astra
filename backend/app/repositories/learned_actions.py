import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearnedAction


class LearnedActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_org(self, org_id: uuid.UUID) -> list[LearnedAction]:
        result = await self.session.execute(
            select(LearnedAction).where(LearnedAction.org_id == org_id)
        )
        return list(result.scalars().all())

    async def add(self, entry: LearnedAction) -> LearnedAction:
        self.session.add(entry)
        await self.session.flush()
        return entry
