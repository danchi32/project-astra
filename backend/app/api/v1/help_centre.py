"""The customer-facing help centre — ASTRA's own support documentation.

Read-only, and open to every authenticated role rather than staff only. The person who
cannot get the agent installed, or who is staring at an error code, is often not an
administrator; gating support content behind a role means the people who need it most
cannot reach it.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import FixedWindowLimiter, RateLimitExceeded, apply_limit
from app.models import User
from app.schemas.assistant import AssistantAsk, AssistantReply, AssistantSource
from app.schemas.help_centre import (
    HELP_CATEGORIES,
    HelpArticleRead,
    HelpArticleSummary,
)
from app.services.ai.support_bot import SupportBot
from app.services.help_centre import HelpCentreService

router = APIRouter(prefix="/help", tags=["help"])


@router.get(
    "/articles",
    response_model=list[HelpArticleSummary],
    summary="Search ASTRA's support articles",
)
async def list_help_articles(
    q: str | None = Query(None, max_length=200, description="Free text over title, body and code"),
    category: str | None = Query(None, max_length=40),
    error_code: str | None = Query(None, max_length=40, description="Exact code, case-insensitive"),
    limit: int = Query(100, ge=1, le=200),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[HelpArticleSummary]:
    articles = await HelpCentreService(session).list_articles(
        q=q, category=category, error_code=error_code, limit=limit
    )
    return [HelpArticleSummary.model_validate(a) for a in articles]


@router.get(
    "/categories",
    response_model=dict[str, int],
    summary="Help categories that have published articles, with counts",
)
async def list_help_categories(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await HelpCentreService(session).categories()


@router.get(
    "/category-options",
    response_model=list[str],
    summary="Every category an article may be filed under",
)
async def list_category_options(
    _: User = Depends(get_current_user),
) -> list[str]:
    """The full vocabulary, including empty sections — the operator's authoring form needs
    the complete list, while `/categories` deliberately reports only what is populated."""
    return HELP_CATEGORIES


@router.get(
    "/articles/{article_id}",
    response_model=HelpArticleRead,
    summary="Read one support article",
)
async def get_help_article(
    article_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> HelpArticleRead:
    article = await HelpCentreService(session).get_article(article_id)
    return HelpArticleRead.model_validate(article)


# One person, asking questions. Generous enough that nobody hits it in a real support
# session, low enough that a script pointed at this endpoint cannot spend the AI budget:
# every call past a cached greeting is a model call. Enforced, unlike the agent limiter —
# there is no heartbeat to lose here, only cost.
_assistant_limiter = FixedWindowLimiter(limit=30, window_seconds=600)


@router.post(
    "/assistant",
    response_model=AssistantReply,
    summary="Ask the support assistant, answered from the documentation",
)
async def ask_assistant(
    body: AssistantAsk,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssistantReply:
    """Answer a question from ASTRA's published help articles and the caller's own
    organization's knowledge base.

    Deliberately not a conversation resource: nothing is stored, and the client replays
    the transcript it holds. A help widget that quietly filed every question into the
    database would be a record of what each employee is struggling with, kept for no
    purpose either of us asked for.
    """
    try:
        apply_limit(_assistant_limiter, str(actor.id), enforce=True, label="user")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have asked a lot of questions in a short time. Try again shortly, "
            "or raise a support request.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    reply = await SupportBot(session).answer(
        question=body.message,
        history=[turn.model_dump() for turn in body.history],
        org_id=actor.org_id,
    )
    return AssistantReply(
        answer=reply.answer,
        sources=[AssistantSource.model_validate(s) for s in reply.sources],
        grounded=reply.grounded,
    )
