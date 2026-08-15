"""ASTRA's own support documentation, as a customer reads it.

Every organization sees exactly the same articles here, and they are the ones the platform
operator wrote. That is the whole security surface of this module, so it is stated once and
enforced in one place: `_published_global()`.

Two filters, both mandatory, both easy to leave off by accident:

  * ``org_id IS NULL`` — an article belonging to an organization is that organization's own
    runbook. Serving one of those here would hand a customer another customer's internal
    documentation.
  * ``published_at IS NOT NULL`` — a draft, or a learned article that has not earned its
    place yet, is not support documentation. The same column already gates what the
    assistant will answer from, so an article is either live in both places or neither.
"""
import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle
from app.services.exceptions import NotFoundError


def _published_global() -> Select:
    """The only starting point any read in this module is allowed to use."""
    return select(KnowledgeArticle).where(
        KnowledgeArticle.org_id.is_(None),
        KnowledgeArticle.published_at.is_not(None),
    )


class HelpCentreService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_articles(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        error_code: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeArticle]:
        """Published support articles, most recently updated first.

        Matching is literal rather than semantic on purpose. Someone arriving here has a
        code on their screen and wants the page about that code; a nearest-neighbour search
        would answer a question they did not ask. The assistant already covers the "I can
        only describe it in my own words" case.
        """
        stmt = _published_global()

        if error_code:
            # Codes are quoted back with inconsistent case ("0X80070005"), and an exact
            # match that fails on capitalisation reads to the user as "not documented".
            stmt = stmt.where(func.lower(KnowledgeArticle.error_code) == error_code.strip().lower())
        if category:
            stmt = stmt.where(KnowledgeArticle.help_category == category)
        if q:
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(or_(
                func.lower(KnowledgeArticle.title).like(like),
                func.lower(KnowledgeArticle.content).like(like),
                func.lower(KnowledgeArticle.error_code).like(like),
            ))

        stmt = stmt.order_by(KnowledgeArticle.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_article(self, article_id: uuid.UUID) -> KnowledgeArticle:
        article = (await self.session.execute(
            _published_global().where(KnowledgeArticle.id == article_id)
        )).scalar_one_or_none()
        if article is None:
            # Deliberately the same answer for "does not exist", "belongs to an
            # organization" and "not published": a distinct error would confirm that some
            # other article exists at that id.
            raise NotFoundError("Help article not found")
        return article

    async def categories(self) -> dict[str, int]:
        """Categories that actually have something published in them.

        Counted rather than hard-coded so a browse UI never offers an empty section — an
        empty category reads as a broken page.
        """
        rows = (await self.session.execute(
            select(KnowledgeArticle.help_category, func.count())
            .where(
                KnowledgeArticle.org_id.is_(None),
                KnowledgeArticle.published_at.is_not(None),
                KnowledgeArticle.help_category.is_not(None),
            )
            .group_by(KnowledgeArticle.help_category)
            .order_by(func.count().desc())
        )).all()
        return {c: n for c, n in rows}
