import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(*, user_id: uuid.UUID, org_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_view_as_token(*, admin_user_id: uuid.UUID, org_id: uuid.UUID, minutes: int = 60) -> str:
    """A short-lived, read-only token for a platform admin to view ONE org's data.
    Carries `view_as` = target org; `sub` stays the real admin (so actions audit to
    them). Writes are blocked centrally while this claim is present."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(admin_user_id),
        "org": str(org_id),
        "role": "admin",
        "view_as": str(org_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.InvalidTokenError on any invalid/expired/non-access token."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def generate_installer_ticket() -> str:
    """A short-lived enrollment ticket for the one-click .exe installer.

    Deliberately shorter than generate_opaque_token: this value is carried in the
    installer's *filename*, where 64 characters are unwieldy and conspicuous. 16
    bytes is 128 bits — far beyond guessing — and the ticket also expires and can be
    revoked, unlike the organization's permanent enrollment key, which is exactly why
    that key is never put in a filename.
    """
    return secrets.token_urlsafe(16)


def hash_opaque_token(token: str) -> str:
    # Opaque secrets (refresh, enrollment, device tokens): only the SHA-256 digest is stored.
    return hashlib.sha256(token.encode()).hexdigest()


# Refresh tokens are one kind of opaque token.
generate_refresh_token = generate_opaque_token
hash_refresh_token = hash_opaque_token
