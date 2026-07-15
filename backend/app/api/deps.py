import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token, hash_opaque_token
from app.models import Device, User, UserRole
from app.repositories.devices import DeviceRepository
from app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _credentials_error
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise _credentials_error
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise _credentials_error

    # "View as organization": a platform admin's read-only token scoped to one org.
    # We detach the user and override org_id so every existing (org-scoped) endpoint
    # transparently returns that org's data. Writes are blocked by the middleware.
    view_as = payload.get("view_as")
    if view_as is not None:
        if not user.is_platform_admin:
            raise _credentials_error
        try:
            target = uuid.UUID(view_as)
        except (ValueError, TypeError):
            raise _credentials_error
        session.expunge(user)          # detached: the org_id override can never persist
        user.org_id = target
        user.role = UserRole.ADMIN     # full read access within the viewed org
        user._view_as = True           # marker for anything that wants to know
    return user


async def get_current_device(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> Device:
    """Authenticates the Windows agent by its opaque device token (agent routes only)."""
    if credentials is None:
        raise _credentials_error
    device = await DeviceRepository(session).get_by_token_hash(
        hash_opaque_token(credentials.credentials)
    )
    if device is None or not device.is_active:
        raise _credentials_error
    return device


async def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """The platform operator (super-admin) — the only identity allowed to manage
    other organizations. Everything they do is audited."""
    if not user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    return user


def require_roles(*roles: UserRole):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency
