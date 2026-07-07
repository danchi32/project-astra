import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnrollmentToken


class EnrollmentTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, token_id: uuid.UUID) -> EnrollmentToken | None:
        return await self.session.get(EnrollmentToken, token_id)

    async def get_by_hash(self, token_hash: str) -> EnrollmentToken | None:
        result = await self.session.execute(
            select(EnrollmentToken).where(EnrollmentToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: uuid.UUID) -> list[EnrollmentToken]:
        result = await self.session.execute(
            select(EnrollmentToken)
            .where(EnrollmentToken.org_id == org_id)
            .order_by(EnrollmentToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def add(self, token: EnrollmentToken) -> EnrollmentToken:
        self.session.add(token)
        await self.session.flush()
        return token
