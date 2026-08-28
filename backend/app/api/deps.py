import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import FixedWindowLimiter, RateLimitExceeded, apply_limit
from app.core.security import decode_access_token, hash_opaque_token
from app.models import Device, User, UserRole
from app.repositories.devices import DeviceRepository
from app.repositories.users import UserRepository

def client_ip(request: Request) -> str:
    """The caller's address, as far as it can be known behind a proxy.

    Cloud Run appends the real client to X-Forwarded-For, so the FIRST entry is the
    client and the rest are proxies. A spoofed header can only make one caller look like
    several; it cannot impersonate somebody else, because this value is only ever
    recorded or counted, never trusted for authorisation.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else "unknown"


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


# One limiter for the whole process, sized from settings at import time.
_agent_limiter = FixedWindowLimiter(
    limit=get_settings().agent_rate_limit_requests,
    window_seconds=get_settings().agent_rate_limit_window_seconds,
)


async def get_rate_limited_device(device: Device = Depends(get_current_device)) -> Device:
    """`get_current_device` plus a per-device rate limit — for the endpoints agents poll.

    Keyed by device id (not IP) so one stuck agent can't affect the rest of an office
    behind the same NAT. Log-only unless ASTRA_AGENT_RATE_LIMIT_ENFORCE is set; see
    app/core/rate_limit.py for why the counter is per-process.
    """
    settings = get_settings()
    if settings.agent_rate_limit_enabled:
        try:
            apply_limit(
                _agent_limiter,
                str(device.id),
                enforce=settings.agent_rate_limit_enforce,
                label="device",
            )
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests from this device. Slow down and retry.",
                headers={"Retry-After": str(exc.retry_after)},
            )
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


def requires(feature: str):
    """Gate an endpoint on the org's plan.

    A dependency, not a check inside the handler and certainly not a hidden nav item: the
    portal hiding a link is presentation, and anyone with the API would still reach the
    feature. This is the same discipline as remediation tiers — the server decides.

    Answers 402 rather than 403 on purpose. The caller has the right role; their plan simply
    doesn't include this, and "ask your administrator" and "upgrade your plan" are different
    sentences with different next steps.
    """

    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        from app.models import Organization
        from app.services.entitlements import EntitlementError, features_for, normalise_plan

        org = await session.get(Organization, user.org_id)
        plan = normalise_plan(org.plan if org else None)
        granted = features_for(org.plan if org else None,
                               org.entitlement_overrides if org else None)
        if feature not in granted:
            err = EntitlementError(feature, plan)
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=str(err),
                headers={"X-Astra-Required-Feature": feature},
            )
        return user

    return dependency


def require_roles(*roles: UserRole):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency
