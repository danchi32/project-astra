import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.users import UserCreate, UserUpdate
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.settings import SettingsService


class UserService:
    """All operations are scoped to the acting user's organization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit = AuditService(session)
        self.settings = SettingsService(session)

    async def _enforce_password_policy(self, org_id: uuid.UUID, password: str) -> None:
        min_length = (await self.settings.ensure(org_id)).min_password_length
        if len(password) < min_length:
            raise ValidationError(
                f"Your organization requires a password of at least {min_length} characters"
            )

    async def create_user(self, *, actor: User, data: UserCreate) -> User:
        if await self.users.get_by_email(data.email) is not None:
            raise ConflictError("A user with this email already exists")
        await self._enforce_password_policy(actor.org_id, data.password)
        user = await self.users.add(
            User(
                org_id=actor.org_id,
                email=data.email.lower(),
                full_name=data.full_name,
                hashed_password=hash_password(data.password),
                role=data.role,
            )
        )
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="user.create",
            target_type="user",
            target_id=str(user.id),
            detail={"email": user.email, "role": user.role.value},
        )
        await self.session.commit()
        return user

    async def list_users(self, *, actor: User) -> list[User]:
        return await self.users.list_by_org(actor.org_id)

    async def get_user(self, *, actor: User, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None or user.org_id != actor.org_id:
            raise NotFoundError("User not found")
        return user

    async def update_user(self, *, actor: User, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = await self.get_user(actor=actor, user_id=user_id)
        changes: dict[str, str | bool] = {}
        if data.full_name is not None:
            user.full_name = data.full_name
            changes["full_name"] = data.full_name
        if data.role is not None:
            user.role = data.role
            changes["role"] = data.role.value
        if data.is_active is not None:
            user.is_active = data.is_active
            changes["is_active"] = data.is_active
            if not data.is_active:
                await self.tokens.revoke_all_for_user(user.id)
        if data.password is not None:
            await self._enforce_password_policy(actor.org_id, data.password)
            user.hashed_password = hash_password(data.password)
            changes["password"] = "changed"
            await self.tokens.revoke_all_for_user(user.id)
        if changes:
            await self.audit.record(
                org_id=actor.org_id,
                actor_id=actor.id,
                action="user.update",
                target_type="user",
                target_id=str(user.id),
                detail=changes,
            )
        await self.session.commit()
        return user

    async def delete_user(self, *, actor: User, user_id: uuid.UUID) -> None:
        user = await self.get_user(actor=actor, user_id=user_id)
        if user.id == actor.id:
            raise ConflictError("You cannot delete your own account")
        email = user.email
        await self.users.delete(user)
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="user.delete",
            target_type="user",
            target_id=str(user_id),
            detail={"email": email},
        )
        await self.session.commit()
