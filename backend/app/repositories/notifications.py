import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get(self, notification_id: uuid.UUID) -> Notification | None:
        return await self.session.get(Notification, notification_id)

    async def list_by_org(
        self, org_id: uuid.UUID, *, unread_only: bool = False, limit: int = 100
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.org_id == org_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_unread(self, org_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                Notification.org_id == org_id, Notification.read_at.is_(None)
            )
        )
        return result.scalar_one()

    async def mark_all_read(self, org_id: uuid.UUID, *, read_at) -> int:
        unread = await self.list_by_org(org_id, unread_only=True, limit=10_000)
        for entry in unread:
            entry.read_at = read_at
        return len(unread)
