"""Invite codes — the gate that keeps organization creation invite-only.

The platform operator issues a code (scripts/create_invite.py or, later, a
super-admin UI); AuthService.register consumes exactly one to create an org.
"""
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_opaque_token, hash_opaque_token
from app.models import InviteCode
from app.models.base import utcnow
from app.repositories.invite_codes import InviteCodeRepository


class InviteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InviteCodeRepository(session)

    async def create(self, *, note: str | None = None, expires_in_days: int = 30) -> tuple[InviteCode, str]:
        """Mint a single-use invite code. Returns (record, raw_code); the raw code
        is shown only here and must be delivered to the new organization."""
        raw = generate_opaque_token()
        record = await self.repo.add(
            InviteCode(
                code_hash=hash_opaque_token(raw),
                note=note,
                expires_at=utcnow() + timedelta(days=expires_in_days),
            )
        )
        await self.session.commit()
        return record, raw
