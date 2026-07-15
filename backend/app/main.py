import uuid

import jwt
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
# auth (login/register/profile), platform (operator), and agent (devices keep
# reporting even when the org is read-only for its human users).
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_UNGATED_PREFIXES = ("/api/v1/auth", "/api/v1/platform", "/api/v1/agent")

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


@app.middleware("http")
async def enforce_org_writable(request: Request, call_next):
    """Block mutating requests when the caller's organization is read-only
    (trial ended, past due, suspended, canceled). Reads always pass; the operator,
    auth, and agent paths are exempt. The org id comes from the JWT's `org` claim."""
    if request.method not in _WRITE_METHODS or not request.url.path.startswith("/api/v1/"):
        return await call_next(request)
    if request.url.path.startswith(_UNGATED_PREFIXES):
        return await call_next(request)

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return await call_next(request)  # let the endpoint's own auth return 401
    try:
        org_id = uuid.UUID(decode_access_token(auth[7:])["org"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return await call_next(request)

    async with database.SessionLocal() as session:
        org = await session.get(Organization, org_id)
    if org is not None and not org_is_writable(org):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"detail": read_only_reason(org)},
        )
    return await call_next(request)


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
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
