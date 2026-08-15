"""The customer-facing help centre — ASTRA's own support documentation.

Read-only, and open to every authenticated role rather than staff only. The person who
cannot get the agent installed, or who is staring at an error code, is often not an
administrator; gating support content behind a role means the people who need it most
cannot reach it.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.help_centre import (
    HELP_CATEGORIES,
    HelpArticleRead,
    HelpArticleSummary,
)
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
