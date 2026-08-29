"""Endpoints reachable without a token, for the marketing website.

Everything else in this API is behind authentication, so this module states its own rules
rather than inheriting them:

  * It reads only what the platform operator has already published — global help articles
    and the built-in FAQ. No organization's data is reachable from here, by construction:
    the bot is given the public scope and the public scope has no org.
  * It writes nothing. There is no conversation record, no lead capture, no counter — a
    chat widget on a public page is an open door, and the less it can create, the less
    there is to abuse.
  * It is rate limited per IP and enforced, because every call that gets past retrieval
    costs a model call, and the caller is a stranger.
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import FixedWindowLimiter, RateLimitExceeded, apply_limit
from app.schemas.assistant import AssistantAsk, AssistantReply, AssistantSource
from app.schemas.public_stats import PublicStats
from app.services.ai.intent import is_off_topic
from app.services.ai.support_bot import SupportBot
from app.services.platform import PlatformService

logger = logging.getLogger("astra.public")

router = APIRouter(prefix="/public", tags=["public"])

_settings = get_settings()

#: The refusal for "write me a poem". `intent.OFF_TOPIC_REPLY` says the same thing in the
#: voice of the in-product IT assistant, which is the wrong voice for a stranger on the
#: marketing site who has never seen the product.
_OFF_TOPIC_REPLY = (
    "I can only help with questions about ASTRA and Technomate IT-Solution — what the "
    "product does, pricing, rollout, security, or getting in touch with the team. "
    "Ask me one of those and I'll do my best."
)

#: Per visitor IP. A real pre-sales conversation is a handful of questions; this leaves
#: room for a curious one and still caps what a single source can spend.
_assistant_limiter = FixedWindowLimiter(
    limit=_settings.public_assistant_rate_limit_requests,
    window_seconds=_settings.public_assistant_rate_limit_window_seconds,
)


@router.post(
    "/assistant",
    response_model=AssistantReply,
    summary="Ask the website assistant about ASTRA (no account required)",
)
async def ask_public_assistant(
    body: AssistantAsk,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> AssistantReply:
    """Answer a visitor's question from the public FAQ and ASTRA's published help articles.

    Never touches customer data, never takes an action, and stores nothing about whoever
    asked.
    """
    try:
        apply_limit(_assistant_limiter, client_ip(request), enforce=True, label="ip")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="That's a lot of questions in a short time. Please try again in a few "
            "minutes, or send us a message through the contact form.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    # The gate that keeps this from being used as a free general-purpose chatbot. It
    # fails open — an unrecognised question still reaches retrieval, and retrieval turning
    # up nothing is itself a cheap refusal, with no model call behind it.
    if is_off_topic(body.message):
        return AssistantReply(answer=_OFF_TOPIC_REPLY, grounded=False)

    reply = await SupportBot(session).answer(
        question=body.message,
        history=[turn.model_dump() for turn in body.history],
        org_id=None,  # the public scope — global articles and the FAQ, nothing else
    )
    return AssistantReply(
        answer=reply.answer,
        sources=[AssistantSource.model_validate(s) for s in reply.sources],
        grounded=reply.grounded,
    )


#: Counts change slowly and every homepage visit asks for them, so the answer is held in
#: memory for a few minutes. Per-instance, which is fine: with N instances the database
#: sees at most N queries per window, and there is no Redis in this backend to share a
#: cache through. A stale count is a smaller problem than a database query per pageview.
_STATS_TTL_SECONDS = 300
_stats_cache: dict[str, object] = {"at": 0.0, "value": None}

#: Looser than the assistant's limit — this costs one cheap aggregate query, not a model
#: call — but present, because an uncached miss still reaches the database.
_stats_limiter = FixedWindowLimiter(limit=60, window_seconds=60)


@router.get(
    "/stats",
    response_model=PublicStats,
    summary="Aggregate platform counts for the marketing site (no account required)",
)
async def public_stats(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> PublicStats:
    """Counts of customer organisations, devices and completed remediations.

    Serves the homepage figures. Everything here is an aggregate over customer
    organisations with the operator's own workspace excluded — no names, no per-customer
    breakdown, nothing that could identify who they are.

    The website reads this at runtime, so the numbers on the page are whatever the
    platform actually holds. That is the entire point: they replace four figures that
    were invented before there was anything real to put there, and they cannot drift,
    because nobody maintains them.
    """
    try:
        apply_limit(_stats_limiter, client_ip(request), enforce=True, label="ip")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    cached = _stats_cache.get("value")
    if cached is not None and time.monotonic() - float(_stats_cache["at"]) < _STATS_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    stats = await PlatformService(session).public_stats()
    _stats_cache["value"] = stats
    _stats_cache["at"] = time.monotonic()
    return stats
