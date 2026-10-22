"""Workforce Insights ("Tracker") — tracked accounts and who they resolve to.

A tracked Windows account (ACME\\rahul) resolves to a person through the device it was seen on:
whoever the device is assigned to in Assets. That assignment is stamped onto each daily summary
at recompute, so this is a read-only view — there is no separate account→person mapping to keep.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.workforce import WorkforceRepository
from app.schemas.workforce import TrackedAccountRead


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkforceRepository(session)

    async def list_accounts(self, *, org_id: uuid.UUID) -> list[TrackedAccountRead]:
        rows = await self.repo.account_rows(org_id)
        # Resolve the names of the mapped users in one query.
        user_ids = {uid for _, uid, _, _ in rows if uid is not None}
        users: dict[uuid.UUID, User] = {}
        if user_ids:
            found = (await self.session.execute(
                select(User).where(User.id.in_(user_ids))
            )).scalars().all()
            users = {u.id: u for u in found}
        return [
            TrackedAccountRead(
                username=username,
                user_id=user_id,
                user_name=users[user_id].full_name if user_id in users else None,
                user_email=users[user_id].email if user_id in users else None,
                last_seen=last_seen,
                device_count=device_count,
            )
            for username, user_id, last_seen, device_count in rows
        ]
