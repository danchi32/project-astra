import secrets
import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    generate_refresh_token,
    hash_opaque_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import (
    Organization,
    PasswordResetToken,
    PendingRegistration,
    RefreshToken,
    User,
    UserRole,
)
from app.models.base import as_utc, utcnow
from app.repositories.invite_codes import InviteCodeRepository
from app.repositories.organizations import OrganizationRepository
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.pending_registrations import PendingRegistrationRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest, RegisterVerifyRequest
from app.services.audit import AuditService
from app.services.email import EmailService
from app.services.exceptions import AuthenticationError, ConflictError, ValidationError
from app.services.settings import SettingsService
from app.services.subscription import TRIAL_DAYS

settings = get_settings()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit = AuditService(session)
        self.orgs = OrganizationRepository(session)
        self.invites = InviteCodeRepository(session)
        self.pending = PendingRegistrationRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)
        self.email = EmailService()

    async def _provision_org(
        self, *, organization_name: str, admin_name: str, email: str, hashed_password: str
    ) -> tuple[Organization, User]:
        """Create the org + its first admin (no commit). Shared by every signup path."""
        org = await self.orgs.add(
            Organization(
                name=organization_name.strip(),
                trial_ends_at=utcnow() + timedelta(days=TRIAL_DAYS),
                agent_enrollment_key=generate_opaque_token(),
            )
        )
        admin = await self.users.add(
            User(
                org_id=org.id,
                email=email,
                full_name=admin_name.strip(),
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await self.audit.record(
            org_id=org.id,
            actor_id=admin.id,
            action="organization.register",
            target_type="organization",
            target_id=str(org.id),
            detail={"name": org.name, "admin_email": email},
        )
        return org, admin

    async def _send_welcome(self, *, to: str, name: str, org_name: str) -> None:
        try:
            await self.email.send_welcome(to=to, name=name, org_name=org_name, trial_days=TRIAL_DAYS)
        except Exception:  # welcome email must never fail the signup
            pass

    async def register(self, data: RegisterRequest) -> tuple[str, str]:
        """Create a NEW organization and its first admin (open self-service signup).
        One transaction: a partial org (no admin) can never exist. An invite code is
        optional — if supplied it must be valid and is consumed."""
        invite = None
        if data.invite_code:
            invite = await self.invites.get_by_hash(hash_opaque_token(data.invite_code))
            if invite is None or invite.used_at is not None or as_utc(invite.expires_at) <= utcnow():
                raise AuthenticationError("Invalid or expired invite code")

        email = data.admin_email.lower()
        if await self.users.get_by_email(email) is not None:
            raise ConflictError("A user with that email already exists")

        org, admin = await self._provision_org(
            organization_name=data.organization_name, admin_name=data.admin_name,
            email=email, hashed_password=hash_password(data.admin_password),
        )
        if invite is not None:
            invite.used_at = utcnow()
            invite.used_by_org_id = org.id

        access = create_access_token(user_id=admin.id, org_id=admin.org_id, role=admin.role.value)
        refresh = await self._issue_refresh_token(admin)
        await self.session.commit()
        await self._send_welcome(to=email, name=admin.full_name, org_name=org.name)
        return access, refresh

    async def register_start(self, data: RegisterRequest) -> tuple[bool, str | None, str | None]:
        """First step of signup. When email is configured, emails a 6-digit code and
        stores the pending signup (no org yet) -> (True, None, None). When email is
        off, creates the org immediately -> (False, access, refresh)."""
        email = data.admin_email.lower()
        if await self.users.get_by_email(email) is not None:
            raise ConflictError("A user with that email already exists")

        if not self.email.enabled:
            access, refresh = await self.register(data)
            return False, access, refresh

        code = f"{secrets.randbelow(1_000_000):06d}"
        await self.pending.delete_by_email(email)
        await self.pending.add(
            PendingRegistration(
                email=email,
                otp_hash=hash_opaque_token(code),
                organization_name=data.organization_name.strip(),
                admin_name=data.admin_name.strip(),
                hashed_password=hash_password(data.admin_password),
                expires_at=utcnow() + timedelta(minutes=settings.otp_ttl_minutes),
            )
        )
        await self.session.commit()
        if not await self.email.send_otp(to=email, code=code):
            raise ValidationError("Couldn't send the verification email. Please try again.")
        return True, None, None

    async def register_verify(self, data: RegisterVerifyRequest) -> tuple[str, str]:
        """Second step: confirm the code, then create the org + admin and log in."""
        email = data.admin_email.lower()
        pending = await self.pending.get_by_email(email)
        if pending is None or as_utc(pending.expires_at) <= utcnow():
            raise ValidationError("Your code has expired. Please start again.")
        if pending.attempts >= 5:
            raise ValidationError("Too many incorrect attempts. Please start again.")
        if hash_opaque_token(data.code.strip()) != pending.otp_hash:
            pending.attempts += 1
            await self.session.commit()
            raise ValidationError("That code isn't right. Check the email and try again.")

        if await self.users.get_by_email(email) is not None:
            await self.pending.delete_by_email(email)
            await self.session.commit()
            raise ConflictError("A user with that email already exists")

        org, admin = await self._provision_org(
            organization_name=pending.organization_name, admin_name=pending.admin_name,
            email=email, hashed_password=pending.hashed_password,
        )
        await self.pending.delete_by_email(email)
        access = create_access_token(user_id=admin.id, org_id=admin.org_id, role=admin.role.value)
        refresh = await self._issue_refresh_token(admin)
        await self.session.commit()
        await self._send_welcome(to=email, name=admin.full_name, org_name=org.name)
        return access, refresh

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
        if record is None or as_utc(record.expires_at) <= utcnow():
            raise AuthenticationError("Invalid or expired refresh token")

        user = await self.users.get(record.user_id)

        # Reuse detection: a token already rotated/revoked but presented again is a
        # replay (the token was stolen). Revoke the ENTIRE family so neither the
        # attacker's nor the victim's chain survives — both must log in again.
        if record.revoked_at is not None:
            if record.family_id is not None:
                await self.tokens.revoke_family(record.family_id)
            if user is not None:
                await self.audit.record(
                    org_id=user.org_id,
                    actor_id=user.id,
                    action="auth.refresh_reuse_detected",
                    target_type="user",
                    target_id=str(user.id),
                )
            await self.session.commit()
            raise AuthenticationError("Invalid or expired refresh token")

        if user is None or not user.is_active:
            raise AuthenticationError("Invalid or expired refresh token")

        # Rotation: a refresh token is single-use; the new one stays in the same family.
        record.revoked_at = utcnow()
        access = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
        new_refresh = await self._issue_refresh_token(user, family_id=record.family_id)
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

    async def request_password_reset(self, email: str) -> None:
        """Email a reset link. Always silent (never reveals whether the account
        exists), and a no-op when email isn't configured."""
        user = await self.users.get_by_email(email.lower())
        if user is None or not user.is_active or not self.email.enabled:
            return

        raw = generate_opaque_token()
        await self.reset_tokens.delete_for_user(user.id)  # only the newest link is valid
        await self.reset_tokens.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_opaque_token(raw),
                expires_at=utcnow() + timedelta(minutes=settings.password_reset_ttl_minutes),
            )
        )
        await self.session.commit()

        link = f"{(settings.public_app_url or '').rstrip('/')}/reset-password?token={raw}"
        try:
            await self.email.send_password_reset(to=user.email, name=user.full_name, link=link)
        except Exception:
            pass

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        record = await self.reset_tokens.get_by_hash(hash_opaque_token(token))
        if record is None or record.used_at is not None or as_utc(record.expires_at) <= utcnow():
            raise ValidationError("This reset link is invalid or has expired. Request a new one.")

        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise ValidationError("This reset link is invalid or has expired. Request a new one.")

        min_length = (await SettingsService(self.session).ensure(user.org_id)).min_password_length
        if len(new_password) < min_length:
            raise ValidationError(f"Password must be at least {min_length} characters")

        user.hashed_password = hash_password(new_password)
        record.used_at = utcnow()
        await self.tokens.revoke_all_for_user(user.id)  # invalidate every existing session
        await self.audit.record(
            org_id=user.org_id,
            actor_id=user.id,
            action="password.reset",
            target_type="user",
            target_id=str(user.id),
        )
        await self.session.commit()
        try:
            await self.email.send_password_changed(to=user.email, name=user.full_name)
        except Exception:
            pass

    async def _issue_refresh_token(self, user: User, family_id: uuid.UUID | None = None) -> str:
        raw = generate_refresh_token()
        await self.tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw),
                expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
                family_id=family_id or uuid.uuid4(),
            )
        )
        return raw
