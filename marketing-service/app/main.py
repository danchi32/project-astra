import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.email import EmailService
from app.services.telegram import TelegramNotifier

settings = get_settings()

# uvicorn only configures its own loggers, so without this every logger.info in this
# service would go to the lastResort handler (WARNING and above) and be discarded —
# including the "lead captured" line, which is the one record that proves the whole
# pipeline is alive. Same fix, same reason, as the product backend.
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# httpx logs every request at INFO as "HTTP Request: POST <full url> ...". For most APIs
# that is useful. For Telegram it is a credential leak: the bot token is a path segment of
# every call — https://api.telegram.org/bot<TOKEN>/sendMessage — so an INFO line writes the
# token into Cloud Run logs on every alert, every approval, every button press.
#
# Raised to WARNING rather than disabled: a genuine transport failure still surfaces, and
# this service already logs its own outcome for each integration in terms that mean
# something ("telegram alert reached none of N chats"), which is the line worth having.
#
# The same shape of leak is latent in any client that puts a secret in a URL. This is the
# reason the marketing service's own intake uses a signed header instead.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Which integrations a running revision actually has is otherwise only knowable by reading
# the deploy that produced it — and "why did nobody get a Telegram alert" is answered here
# in one line. Values are never logged, only whether they are present.
logging.getLogger("astra.mkt.startup").info(
    "starting environment=%s intake=%s admin=%s n8n=%s telegram=%s scoring=%s bigin=%s email=%s",
    settings.environment,
    bool(settings.intake_secret),
    bool(settings.admin_token),
    bool(settings.n8n_lead_webhook_url),
    # Ask the services themselves rather than re-deriving their conditions here. This line
    # once reported email=False while SMTP was configured and acknowledgements were going
    # out, because it only checked for a Resend key — the one diagnostic whose whole job is
    # to answer "why did nobody get an email" was the thing giving the wrong answer.
    TelegramNotifier().enabled,
    bool(settings.anthropic_api_key),
    bool(settings.bigin_refresh_token),
    EmailService().enabled,
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "ASTRA Marketing Service — system of record for leads, content and approvals. "
        "Deliberately separate from the product API: this service holds marketing "
        "credentials and a public intake endpoint, and neither belongs in the service "
        "that executes commands on customer endpoints."
    ),
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    """Liveness for Cloud Run. Deliberately does not touch the database.

    A health check that queries Postgres turns a Neon cold start into a failed check and
    a restarted revision, which is the opposite of helpful. Readiness of the data layer is
    proven by the intake endpoint itself.
    """
    return JSONResponse({"status": "ok", "service": "marketing", "env": settings.environment})


@app.get("/", include_in_schema=False)
async def root() -> PlainTextResponse:
    return PlainTextResponse("ASTRA Marketing Service")
