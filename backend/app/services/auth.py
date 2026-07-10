from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.models.base import as_utc, utcnow
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.services.audit import AuditService
from app.services.exceptions import AuthenticationError, ValidationError
from app.services.settings import SettingsService


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit = AuditService(session)

    async def login(self, email: str, password: str) -> tuple[str, str]:
        user = await self.users.get_by_email(email)
        # Verify even when the user is missing so response timing doesn't leak account existence.
        password_ok = verify_password(password, user.hashed_password if user else "$2b$12$" + "x" * 53)
        if user is None or not password_ok or not user.is_active:
            raise AuthenticationError("Invalid email or password")

        access = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
        refresh = await self._issue_refresh_token(user)
        await self.audit.record(
            org_id=user.org_id,
            actor_id=user.id,
            action="auth.login",
            target_type="user",
            target_id=str(user.id),
        )
        await self.session.commit()
        return access, refresh

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        record = await self.tokens.get_by_hash(hash_refresh_token(refresh_token))
        if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= utcnow():
            raise AuthenticationError("Invalid or expired refresh token")

        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid or expired refresh token")

        # Rotation: a refresh token is single-use.
        record.revoked_at = utcnow()
        access = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
        new_refresh = await self._issue_refresh_token(user)
        await self.session.commit()
        return access, new_refresh

    async def logout(self, refresh_token: str) -> None:
        record = await self.tokens.get_by_hash(hash_refresh_token(refresh_token))
        if record is not None and record.revoked_at is None:
            record.revoked_at = utcnow()
            await self.audit.record(
                org_id=(await self.users.get(record.user_id)).org_id,
                actor_id=record.user_id,
                action="auth.logout",
                target_type="user",
                target_id=str(record.user_id),
            )
        # Idempotent: logging out an unknown/revoked token is not an error.
        await self.session.commit()

    async def update_profile(self, *, user: User, full_name: str) -> User:
        user.full_name = full_name
        await self.audit.record(
            org_id=user.org_id,
            actor_id=user.id,
            action="profile.update",
            target_type="user",
            target_id=str(user.id),
            detail={"full_name": full_name},
        )
        await self.session.commit()
        return user

    async def change_password(
        self, *, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise ValidationError("Your current password is incorrect")

        min_length = (await SettingsService(self.session).ensure(user.org_id)).min_password_length
        if len(new_password) < min_length:
            raise ValidationError(
                f"Your organization requires a password of at least {min_length} characters"
            )

        user.hashed_password = hash_password(new_password)
        # Force re-login everywhere else — a password change invalidates old sessions.
        await self.tokens.revoke_all_for_user(user.id)
        await self.audit.record(
            org_id=user.org_id,
            actor_id=user.id,
            action="password.change",
            target_type="user",
            target_id=str(user.id),
        )
        await self.session.commit()

    async def _issue_refresh_token(self, user: User) -> str:
        settings = get_settings()
        raw = generate_refresh_token()
        await self.tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw),
                expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
            )
        )
        return raw
