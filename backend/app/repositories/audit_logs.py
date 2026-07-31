import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entry: AuditLog) -> AuditLog:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_page(
        self, org_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        """One page of the org's audit trail, newest first, plus the total match count."""
        from app.schemas.pagination import paginate

        stmt = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id)
            .order_by(AuditLog.created_at.desc())
        )
        rows, total, _, _ = await paginate(
            self.session, stmt, page=offset // max(1, limit) + 1, page_size=limit
        )
        return rows, total

    async def list_by_org(self, org_id: uuid.UUID, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.org_id == org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
