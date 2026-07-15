from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PendingRegistration


class PendingRegistrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> PendingRegistration | None:
        result = await self.session.execute(
            select(PendingRegistration).where(PendingRegistration.email == email)
        )
        return result.scalar_one_or_none()

    async def delete_by_email(self, email: str) -> None:
        await self.session.execute(
            delete(PendingRegistration).where(PendingRegistration.email == email)
        )

    async def add(self, pending: PendingRegistration) -> PendingRegistration:
        self.session.add(pending)
        await self.session.flush()
        return pending
