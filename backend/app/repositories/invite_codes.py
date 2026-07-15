import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InviteCode


class InviteCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_hash(self, code_hash: str) -> InviteCode | None:
        result = await self.session.execute(
            select(InviteCode).where(InviteCode.code_hash == code_hash)
        )
        return result.scalar_one_or_none()

    async def add(self, invite: InviteCode) -> InviteCode:
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def list_all(self) -> list[InviteCode]:
        result = await self.session.execute(select(InviteCode).order_by(InviteCode.created_at))
        return list(result.scalars().all())

    async def get(self, invite_id: uuid.UUID) -> InviteCode | None:
        return await self.session.get(InviteCode, invite_id)
