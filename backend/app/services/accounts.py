"""Workforce Insights ("Tracker") — account → directory-user mapping.

Resolving a tracked Windows account (ACME\\rahul) to a person, so attendance and productivity
can be grouped by user and team and shown back to the employee. The mapping in
`activity_accounts` is the source of truth; `daily_user_summary.user_id` is a copy that each
recompute refreshes, and an assignment also backfills the account's already-computed days.

Org-scoped and audited, same discipline as the other Tracker services.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.workforce import WorkforceRepository
from app.schemas.workforce import AccountAssignWrite, TrackedAccountRead
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkforceRepository(session)
        self.audit = AuditService(session)

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

    async def assign(self, *, actor: User, body: AccountAssignWrite) -> TrackedAccountRead:
        username = body.username.strip().lower()  # accounts are stored lower-cased on ingest
        user: User | None = None
        if body.user_id is not None:
            user = await self.session.get(User, body.user_id)
            if user is None or user.org_id != actor.org_id:
                raise NotFoundError("User not found.")

        await self.repo.upsert_account(actor.org_id, username, body.user_id)
        # Backfill the person onto this account's existing days so rollups and self-view reflect
        # it immediately, not only from the next recompute.
        updated = await self.repo.set_summary_user(actor.org_id, username, body.user_id)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="activity_account.assign",
            target_type="activity_account", target_id=username,
            detail={"username": username, "user_id": str(body.user_id) if body.user_id else None,
                    "backfilled_days": updated},
        )
        await self.session.commit()

        # Return the account's current row from the canonical list.
        for row in await self.list_accounts(org_id=actor.org_id):
            if row.username == username:
                return row
        # No attendance yet for this account — report the bare mapping back.
        return TrackedAccountRead(
            username=username, user_id=body.user_id,
            user_name=user.full_name if user else None,
            user_email=user.email if user else None,
            last_seen=None, device_count=0,
        )
