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

# Write methods on these path prefixes are NOT gated by subscription status:
# auth (login/register/profile), platform (operator), agent (devices keep
# reporting even when the org is read-only for its human users), and billing
# (a read-only org must still be able to reach Checkout to pay and reactivate).
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_UNGATED_PREFIXES = ("/api/v1/auth", "/api/v1/platform", "/api/v1/agent", "/api/v1/billing")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="ASTRA — Enterprise AI Operations Platform backend API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    # Secret-free diagnostics (booleans / presence only — never any values).
    import os

    from app.services.email import EmailService

    keys = [
        "ASTRA_SMTP_HOST", "ASTRA_SMTP_USER", "ASTRA_SMTP_PASSWORD",
        "ASTRA_SMTP_PORT", "ASTRA_EMAIL_FROM", "ASTRA_PUBLIC_APP_URL",
        "ASTRA_JWT_SECRET_KEY",  # control: known-working user-set var
    ]
    return {
        "status": "ok",
        "service": settings.app_name,
        "email_enabled": EmailService().enabled,
        "settings_read": {
            "smtp_host": bool(settings.smtp_host),
            "smtp_user": bool(settings.smtp_user),
            "smtp_password": bool(settings.smtp_password),
            "public_app_url": settings.public_app_url,
        },
        # Is the raw variable present in THIS process's environment at all?
        "in_os_environ": {k: (k in os.environ) for k in keys},
    }


@app.get("/health/email-check", include_in_schema=False)
async def email_check() -> dict[str, object]:
    """Diagnostic: raw TCP reachability (IPv4 vs IPv6) + SMTP auth. No email sent,
    no secrets. Distinguishes an IPv6-route problem from a blocked-SMTP problem."""
    import socket

    from fastapi.concurrency import run_in_threadpool

    from app.services.email import EmailService

    host, port = settings.smtp_host, settings.smtp_port

    def tcp(family: int) -> str:
        try:
            infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
            if not infos:
                return "no address"
            af, st, proto, _c, sa = infos[0]
            s = socket.socket(af, st, proto)
            s.settimeout(10)
            s.connect(sa)
            s.close()
            return "ok"
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def tcp_to(h: str, p: int) -> str:
        try:
            infos = socket.getaddrinfo(h, p, socket.AF_INET, socket.SOCK_STREAM)
            af, st, proto, _c, sa = infos[0]
            s = socket.socket(af, st, proto)
            s.settimeout(8)
            s.connect(sa)
            s.close()
            return "ok"
        except Exception as exc:
            return f"{type(exc).__name__}"

    def probe() -> dict:
        ok, detail = EmailService().verify_connection()
        return {
            "configured_host": host,
            "configured_port": port,
            "smtp_auth_ok": ok,
            "smtp_detail": detail,
            "reachability_ipv4": {
                f"{host}:465": tcp_to(host, 465),
                f"{host}:587": tcp_to(host, 587),
                f"{host}:25": tcp_to(host, 25),
                "api.resend.com:443 (egress control)": tcp_to("api.resend.com", 443),
            },
        }

    return await run_in_threadpool(probe)
