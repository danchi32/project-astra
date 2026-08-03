import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle, KnowledgeSource


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, article_id: uuid.UUID) -> KnowledgeArticle | None:
        return await self.session.get(KnowledgeArticle, article_id)

    async def list_by_org(self, org_id: uuid.UUID) -> list[KnowledgeArticle]:
        result = await self.session.execute(
            select(KnowledgeArticle)
            .where(KnowledgeArticle.org_id == org_id)
            .order_by(KnowledgeArticle.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_learned(
        self, *, org_id: uuid.UUID, action_id: str
    ) -> KnowledgeArticle | None:
        """The org's learned article for one topic, if it has one. Scoped to learned rows
        so a hand-written runbook is never silently rewritten by the learning path."""
        result = await self.session.execute(
            select(KnowledgeArticle).where(
                KnowledgeArticle.org_id == org_id,
                KnowledgeArticle.action_id == action_id,
                KnowledgeArticle.source == KnowledgeSource.RESOLVED_ISSUE,
            )
        )
        return result.scalars().first()

    async def list_global(self) -> list[KnowledgeArticle]:
        """Operator-curated articles (org_id IS NULL) shared with every org."""
        result = await self.session.execute(
            select(KnowledgeArticle)
            .where(KnowledgeArticle.org_id.is_(None))
            .order_by(KnowledgeArticle.created_at.desc())
        )
        return list(result.scalars().all())

    async def add(self, article: KnowledgeArticle) -> KnowledgeArticle:
        self.session.add(article)
        await self.session.flush()
        return article

    async def delete(self, article: KnowledgeArticle) -> None:
        await self.session.delete(article)
