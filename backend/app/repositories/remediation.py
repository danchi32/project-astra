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

    async def list_page(
        self,
        org_id: uuid.UUID,
        *,
        device_id: uuid.UUID | None = None,
        status: list[RemediationStatus] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RemediationTask], int]:
        """One page of the org's remediation tasks, newest first.

        `device_id` exists so a caller that only cares about one machine asks for one
        machine. The device page used to pull the org's entire task list and filter it in
        the browser, which silently becomes "the most recent page of tasks, filtered" the
        moment this endpoint is paged — showing a device as idle while work is queued on it.
        """
        from app.schemas.pagination import paginate

        stmt = select(RemediationTask).where(RemediationTask.org_id == org_id)
        if device_id is not None:
            stmt = stmt.where(RemediationTask.device_id == device_id)
        if status:
            stmt = stmt.where(RemediationTask.status.in_(status))
        stmt = stmt.order_by(RemediationTask.created_at.desc())
        rows, total, _, _ = await paginate(
            self.session, stmt, page=offset // max(1, limit) + 1, page_size=limit
        )
        return rows, total

    async def count_by_status(self, org_id: uuid.UUID) -> dict[str, int]:
        """Org-wide task counts per status, for the dashboard's breakdown chart.

        Its own query rather than tallying a fetched list: once the list is paged, counting
        the rows on screen would chart "the last 50 tasks" while looking exactly like a
        chart of everything.
        """
        rows = (await self.session.execute(
            select(RemediationTask.status, func.count())
            .where(RemediationTask.org_id == org_id)
            .group_by(RemediationTask.status)
        )).all()
        return {r[0].value if hasattr(r[0], "value") else str(r[0]): int(r[1]) for r in rows}

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
