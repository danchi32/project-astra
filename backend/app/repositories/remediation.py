import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RemediationStatus, RemediationTask


class RemediationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, task_id: uuid.UUID) -> RemediationTask | None:
        return await self.session.get(RemediationTask, task_id)

    async def add(self, task: RemediationTask) -> RemediationTask:
        self.session.add(task)
        await self.session.flush()
        return task

    async def list_by_org(self, org_id: uuid.UUID, limit: int = 200) -> list[RemediationTask]:
        result = await self.session.execute(
            select(RemediationTask)
            .where(RemediationTask.org_id == org_id)
            .order_by(RemediationTask.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_recent_for_org(self, org_id: uuid.UUID, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(RemediationTask)
            .where(RemediationTask.org_id == org_id, RemediationTask.created_at >= since)
        )
        return int(result.scalar_one())

    async def find_in_flight(
        self,
        *,
        device_id: uuid.UUID,
        action_id: str,
        params: dict | None,
        not_before: datetime,
    ) -> RemediationTask | None:
        """The same work already queued or running on this device, if any.

        Matched on params too, so pushing KB5094126 and KB5100998 are two different jobs
        while pushing "all pending updates" twice is one.

        ``not_before`` bounds how long a dispatched task can hold the slot. Without it a
        device whose agent died mid-action could never be given that action again — the
        guard would become a permanent lock on the one action you most need to retry.
        """
        result = await self.session.execute(
            select(RemediationTask)
            .where(
                RemediationTask.device_id == device_id,
                RemediationTask.action_id == action_id,
                RemediationTask.status.in_(
                    (
                        RemediationStatus.PENDING_APPROVAL,
                        RemediationStatus.APPROVED,
                        RemediationStatus.DISPATCHED,
                    )
                ),
                RemediationTask.created_at >= not_before,
            )
            .order_by(RemediationTask.created_at.desc())
        )
        for task in result.scalars().all():
            if (task.params or None) == (params or None):
                return task
        return None

    async def list_approved_for_device(self, device_id: uuid.UUID) -> list[RemediationTask]:
        result = await self.session.execute(
            select(RemediationTask)
            .where(
                RemediationTask.device_id == device_id,
                RemediationTask.status == RemediationStatus.APPROVED,
            )
            .order_by(RemediationTask.created_at)
        )
        return list(result.scalars().all())
