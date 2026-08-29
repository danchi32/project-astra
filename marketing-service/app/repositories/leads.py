import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadSubmission


class LeadRepository:
    """Data access for leads and their submissions.

    Adds and flushes but never commits — the caller owns the transaction, so a lead and
    its submission are written together or not at all. A submission without its lead would
    be an orphaned form fill nobody could act on.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, lead_id: uuid.UUID) -> Lead | None:
        return await self.session.get(Lead, lead_id)

    async def get_with_submissions(self, lead_id: uuid.UUID) -> Lead | None:
        stmt = (
            select(Lead)
            .where(Lead.id == lead_id)
            .options(selectinload(Lead.submissions))
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_email(self, email: str) -> Lead | None:
        """Look up by the already-lowercased address.

        Lowercasing happens at the service boundary rather than here so there is exactly
        one place that decides what "the same person" means.
        """
        stmt = select(Lead).where(Lead.email == email)
        return (await self.session.execute(stmt)).scalars().first()

    async def add(self, lead: Lead) -> Lead:
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def add_submission(self, submission: LeadSubmission) -> LeadSubmission:
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def list_recent(self, *, limit: int = 50, offset: int = 0) -> list[Lead]:
        stmt = select(Lead).order_by(Lead.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_undispatched(
        self, *, older_than_seconds: int = 60, limit: int = 100
    ) -> list[LeadSubmission]:
        """Submissions the downstream automation never acknowledged.

        This is the replay queue that makes n8n a nice-to-have rather than a dependency.
        The age floor stops it racing the inline dispatch that fires moments after intake:
        without it, a submission would be picked up twice — once by the request that
        created it and once by the sweeper — and the prospect would get two emails.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        stmt = (
            select(LeadSubmission)
            .where(LeadSubmission.dispatched_at.is_(None))
            .where(LeadSubmission.created_at < cutoff)
            .order_by(LeadSubmission.created_at)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_unsynced(self, *, limit: int = 25) -> list[Lead]:
        """Leads that have never reached the CRM, oldest first.

        Oldest first because a lead that has been waiting longest is the one whose sales
        response is most overdue — a newest-first sweeper would starve exactly the rows
        that most need attention.
        """
        stmt = (
            select(Lead)
            .where(Lead.crm_record_id.is_(None))
            .order_by(Lead.created_at)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
