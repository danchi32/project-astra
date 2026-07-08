import uuid

from sqlalchemy import select
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
