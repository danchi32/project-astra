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

    **The caller is told nothing; the log is told why.** Three different mistakes produce
    this same 401 — no header at all, a header with the wrong scheme, and a correct scheme
    with the wrong token — and they need three different fixes. Left undistinguished they
    cost an afternoon: an n8n Header Auth credential set to the bare token instead of
    `Bearer <token>` sends a header the operator can see is present and correct, and the
    server says only "Not authorised". So the reason goes to the log, where it is useful,
    and never into the response, where it would help someone probing the endpoint.

    The presented value is never logged. It is a guess at a secret, and writing guesses
    into logs is how a secret ends up somewhere it was never stored.
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
        logger.warning("admin request refused: %s", _why(authorization, presented))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorised.",
            headers={"WWW-Authenticate": "Bearer"},
        )


#: Schemes safe to name in a log because they are public constants, not secrets. Anything
#: outside this list is described rather than quoted — see `_why`.
_KNOWN_SCHEMES = frozenset({"basic", "bearer", "digest", "negotiate", "token", "apikey"})


def _why(authorization: str | None, presented: str) -> str:
    """Name the mistake, without quoting any part of the credential.

    The first version of this echoed `authorization.split(" ")[0]` as "the scheme" — which
    is the whole header when there is no space in it, and a header with no space is
    exactly the bare-token misconfiguration this function exists to diagnose. So the one
    case it was written for was the one case that logged the secret. It now names a scheme
    only when the scheme is a public constant, and otherwise describes the shape.

    Length is reported rather than content. It separates "wrong token" from "right token,
    wrong shape" — the distinction that decides what you go and change — while revealing
    nothing usable to anyone who is not already reading our logs.
    """
    if not authorization:
        return "no Authorization header was sent"

    if not presented:
        scheme, space, _ = authorization.partition(" ")
        if not space:
            return (
                "the Authorization header has no scheme prefix — it looks like a bare "
                "token. A Header Auth credential must carry the value 'Bearer <token>', "
                "not the token on its own"
            )
        named = scheme.lower() if scheme.lower() in _KNOWN_SCHEMES else "an unrecognised"
        return (
            f"the Authorization header used {named} scheme, not 'Bearer'. It must carry "
            "the value 'Bearer <token>'"
        )

    expected = len(settings.admin_token)
    if len(presented) != expected:
        return (
            f"the bearer token is {len(presented)} characters; this service expects "
            f"{expected}. Likely a different token, or one copied with whitespace"
        )
    return "the bearer token is the right length but does not match"
