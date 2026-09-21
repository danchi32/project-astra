import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OPEN_STATUSES, RemoteSession, RemoteSessionStatus


class RemoteSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, session_id: uuid.UUID) -> RemoteSession | None:
        return await self.session.get(RemoteSession, session_id)

    async def add(self, remote_session: RemoteSession) -> RemoteSession:
        self.session.add(remote_session)
        await self.session.flush()
        return remote_session

    async def open_for_device(self, device_id: uuid.UUID) -> RemoteSession | None:
        """The session already in flight on this device, if there is one.

        One at a time, per device. Two technicians driving the same mouse is not a feature,
        and a second prompt arriving while the first is still on screen teaches people to
        click Allow to make the dialogs go away.
        """
        result = await self.session.execute(
            select(RemoteSession)
            .where(
                RemoteSession.device_id == device_id,
                RemoteSession.status.in_(list(OPEN_STATUSES)),
            )
            .order_by(RemoteSession.requested_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def list_page(
        self,
        org_id: uuid.UUID,
        *,
        device_id: uuid.UUID | None = None,
        status: list[RemoteSessionStatus] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RemoteSession], int]:
        """One page of the org's remote sessions, newest first, with the total."""
        filters = [RemoteSession.org_id == org_id]
        if device_id is not None:
            filters.append(RemoteSession.device_id == device_id)
        if status:
            filters.append(RemoteSession.status.in_(status))

        total = await self.session.scalar(
            select(func.count()).select_from(RemoteSession).where(*filters)
        )
        result = await self.session.execute(
            select(RemoteSession)
            .where(*filters)
            .order_by(RemoteSession.requested_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total or 0)
