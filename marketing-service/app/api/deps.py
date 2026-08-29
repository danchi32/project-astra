"""Shared FastAPI dependencies."""
import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger("astra.mkt.deps")
settings = get_settings()


async def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Gate the endpoints that return personal data.

    The lead tables hold names, work emails, phone numbers and free-text messages from
    real people. Anything reading them needs a credential, and the absence of a configured
    credential closes the door rather than opening it — the failure mode of the opposite
    choice is a public list of every prospect the company has.

    Compared in constant time so the token cannot be recovered a character at a time.
    """
    if not settings.admin_token:
        logger.error("admin endpoint called but ASTRA_MKT_ADMIN_TOKEN is not set")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative access is not configured.",
        )

    prefix = "Bearer "
    presented = authorization[len(prefix):] if (authorization or "").startswith(prefix) else ""
    if not hmac.compare_digest(presented, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorised.",
            headers={"WWW-Authenticate": "Bearer"},
        )
