import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.v1.router import api_router
from app.core import database
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.models import Organization
from app.services.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.services.subscription import org_is_writable, read_only_reason

settings = get_settings()

# Nothing had ever configured the root logger, and uvicorn only configures its own — so
# every logger.info in this codebase went to the lastResort handler, which starts at
# WARNING, and was discarded. Rate-limit notices, unresolved ticket requesters, remediation
# progress: all written, none of it ever reaching Cloud Logging. Found while trying to read
# the token counters the AI provider now reports, which would have vanished the same way.
# uvicorn's own loggers do not propagate, so this adds our records without duplicating its.
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Which model a running revision is actually answering with is otherwise only knowable by
# reading the deploy that produced it. It is the first thing worth having when a reply
# looks wrong, and the first thing to check after changing the model or rolling one back.
# It doubles as proof the line above works: no app record reached production before it.
logging.getLogger("astra.startup").info(
    "starting environment=%s ai_model=%s ai_configured=%s max_tokens=%s",
    settings.environment, settings.ai_model,
    bool(settings.anthropic_api_key), settings.ai_max_tokens,
)

# Write methods on these path prefixes are NOT gated by subscription status:
# auth (login/register/profile), platform (operator), agent (devices keep
# reporting even when the org is read-only for its human users), and billing
# (a read-only org must still be able to reach Checkout to pay and reactivate).
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# `/help` is a POST only because the support assistant takes a question in a body; it
# creates nothing. Locking it behind the subscription gate would take the help widget away
# from exactly the organization most likely to need it — the one whose trial just ended and
# who is trying to find out what to do about it.
_UNGATED_PREFIXES = (
    "/api/v1/auth", "/api/v1/platform", "/api/v1/agent", "/api/v1/billing", "/api/v1/help",
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="ASTRA — Enterprise AI Operations Platform backend API",
)

app.add_middleware(
    CORSMiddleware,
    # The portal's origin plus the marketing site's — the latter calls /api/v1/public/*
    # directly from the browser, having no server of its own to proxy through.
    allow_origins=[*settings.cors_origins, *settings.marketing_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # allow_headers governs the REQUEST side; a browser cannot read a response header
    # unless it is exposed. The portal needs Content-Disposition to save the .exe
    # installer under the name the server chose — that name carries the enrollment
    # ticket, so getting it wrong produces an installer that cannot enrol.
    expose_headers=["Content-Disposition"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/.well-known/security.txt", include_in_schema=False)
async def security_txt() -> PlainTextResponse:
    expires = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        f"Contact: {settings.security_contact}\n"
        f"Expires: {expires}\n"
        "Preferred-Languages: en\n"
        f"Canonical: {settings.public_api_url}/.well-known/security.txt\n"
    )
    return PlainTextResponse(body, media_type="text/plain")


@app.middleware("http")
async def enforce_org_writable(request: Request, call_next):
    """Block mutating requests when (a) the caller is a platform admin in read-only
    "view as organization" mode, or (b) the caller's organization is read-only
    (trial ended, past due, suspended, canceled). Reads always pass; the operator,
    auth, and agent paths are exempt from (b). The org id comes from the JWT `org`."""
    if request.method not in _WRITE_METHODS or not request.url.path.startswith("/api/v1/"):
        return await call_next(request)

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return await call_next(request)  # let the endpoint's own auth return 401
    try:
        payload = decode_access_token(auth[7:])
        org_id = uuid.UUID(payload["org"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return await call_next(request)

    # (a) "View as" tokens are strictly read-only, on every path.
    if payload.get("view_as"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Read-only: you are viewing this organization as a platform admin."},
        )

    # (b) Subscription gate — exempt operator/auth/agent/billing paths.
    if request.url.path.startswith(_UNGATED_PREFIXES):
        return await call_next(request)
    async with database.SessionLocal() as session:
        org = await session.get(Organization, org_id)
    if org is not None and not org_is_writable(org):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"detail": read_only_reason(org)},
        )
    return await call_next(request)


# Defined last so it is the OUTERMOST middleware — every response (including the
# gate's own 402/403 short-circuits) gets the hardening headers.
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline hardening headers. HSTS is meaningful over HTTPS (Railway/Vercel
    terminate TLS); the rest are safe defaults for an API + its browser clients."""
    response = await call_next(request)
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.get("/health", tags=["system"], summary="Liveness probe")
async def health() -> dict[str, object]:
    from app.services.ai.provider import last_auth_error
    from app.services.email import EmailService

    # Minimal, non-sensitive liveness signal (booleans and a timestamp — no secrets).
    return {
        "status": "ok",
        "service": settings.app_name,
        "email_enabled": EmailService().enabled,
        "ai_enabled": bool(settings.anthropic_api_key),  # False -> AI runs on the stub
        # A key can be configured and still be refused, which is exactly what happened:
        # ai_enabled stayed true for weeks while every call came back 401. This is when
        # this process last saw that, so "configured" and "working" can be told apart.
        "ai_auth_error_at": last_auth_error(),
    }
