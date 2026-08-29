"""The Telegram webhook — this service's second public write endpoint.

The first one, lead intake, is HMAC-signed over the body because it is called by our own
PHP. This one cannot be: Telegram signs nothing. What Telegram offers instead is a secret
of our choosing, echoed back in a header on every update it delivers, and that is the
whole of the transport-level proof available. So this endpoint is built to make that one
check impossible to skip and impossible to weaken:

* **Unset secret means shut, not open.** Identical to `intake_secret` and `admin_token`.
  A missing credential must never be the thing that produces a public endpoint able to
  approve marketing copy.
* **Compared in constant time**, so the secret cannot be recovered a character at a time.
* **The header proves the caller; the allowlist proves the human.** The second check
  lives in the desk, on `from.id`, because anyone in the world can message a bot and
  Telegram will faithfully deliver it. The bot token also sits in the webhook URL, which
  ends up in proxy logs — so the URL is not a credential either.

And one behavioural rule that is easy to get wrong: **answer 200 fast, always.** Telegram
redelivers any update it does not get a prompt answer to. An exception escaping the
handler would turn a single bug into an endless retry loop, and a slow model call inline
would do the same. So the desk never raises, and a rewrite is handed to a background task
that runs after the response has gone out.
"""
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.approval_desk import ApprovalDesk, redraft_and_repost

logger = logging.getLogger("astra.mkt.api.telegram")
settings = get_settings()

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook", status_code=status.HTTP_200_OK, include_in_schema=False,
             summary="Updates from the approval desk")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Take one update from Telegram.

    Not in the OpenAPI schema: it is not an interface anyone else should call, and
    publishing its shape only helps someone probe it.
    """
    if not settings.telegram_webhook_secret:
        logger.error("telegram webhook called but ASTRA_MKT_TELEGRAM_WEBHOOK_SECRET is unset")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The approval desk is not configured.",
        )

    if not hmac.compare_digest(
        x_telegram_bot_api_secret_token or "", settings.telegram_webhook_secret
    ):
        # Logged without the presented value: it is a guess at a secret, and writing
        # guesses into logs is how a secret ends up somewhere it was never stored.
        logger.warning("telegram webhook rejected: bad or missing secret token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorised.")

    try:
        update = await request.json()
    except ValueError:
        # 200, deliberately. A body we cannot parse will not parse on redelivery either,
        # and refusing it would have Telegram send it back forever.
        logger.warning("telegram webhook received a non-JSON body")
        return {"ok": True}

    if not isinstance(update, dict):
        return {"ok": True}

    result = await ApprovalDesk(session).handle_update(update)

    # The rewrite deliberately does NOT get this session. It runs after the response has
    # been sent, by which time the request's session is closed — so it opens its own.

    if result.redraft_item_id is not None:
        background.add_task(redraft_and_repost, result.redraft_item_id)

    return {"ok": True, "handled": result.handled, "note": result.note}
