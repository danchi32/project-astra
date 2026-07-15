import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle, KnowledgeSource, User
from app.repositories.knowledge import KnowledgeRepository
from app.services.ai.embeddings import EmbeddingProvider, cosine_similarity, get_embedding_provider
from app.services.exceptions import NotFoundError


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider | None = None) -> None:
        self.session = session
        self.repo = KnowledgeRepository(session)
        self.embed = provider or get_embedding_provider()

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        title: str,
        content: str,
        source: KnowledgeSource = KnowledgeSource.MANUAL,
        actor_user_id: uuid.UUID | None = None,
    ) -> KnowledgeArticle:
        vector = await self.embed.embed(f"{title}\n{content}")
        article = await self.repo.add(
            KnowledgeArticle(
                org_id=org_id, title=title, content=content, embedding=vector,
                source=source, created_by_user_id=actor_user_id,
            )
        )
        await self.session.commit()
        return article

    async def list_for_org(self, *, org_id: uuid.UUID) -> list[KnowledgeArticle]:
        return await self.repo.list_by_org(org_id)

    async def delete(self, *, actor: User, article_id: uuid.UUID) -> None:
        article = await self.repo.get(article_id)
        if article is None or article.org_id != actor.org_id:
            raise NotFoundError("Knowledge article not found")
        await self.repo.delete(article)
        await self.session.commit()

    # -- Global (platform-operator) articles, shared with every organization ----

    async def create_global(
        self, *, title: str, content: str, actor_user_id: uuid.UUID | None = None
    ) -> KnowledgeArticle:
        vector = await self.embed.embed(f"{title}\n{content}")
        article = await self.repo.add(
            KnowledgeArticle(
                org_id=None, title=title, content=content, embedding=vector,
                source=KnowledgeSource.MANUAL, created_by_user_id=actor_user_id,
            )
        )
        await self.session.commit()
        return article

    async def list_global(self) -> list[KnowledgeArticle]:
        return await self.repo.list_global()

    async def delete_global(self, *, article_id: uuid.UUID) -> None:
        article = await self.repo.get(article_id)
        if article is None or article.org_id is not None:
            raise NotFoundError("Global knowledge article not found")
        await self.repo.delete(article)
        await self.session.commit()

    async def search(
        self, *, org_id: uuid.UUID, query: str, limit: int = 3
    ) -> list[KnowledgeArticle]:
        """Return the most relevant articles for a query, best-first — the org's own
        articles AND the operator's global ones, so a fix the platform adds helps
        every organization."""
        query_vec = await self.embed.embed(query)
        candidates = await self.repo.list_by_org(org_id)
        candidates += await self.repo.list_global()
        scored = [(cosine_similarity(query_vec, a.embedding), a) for a in candidates]
        # Keep only somewhat-relevant matches, best first.
        scored = [pair for pair in scored if pair[0] > 0.2]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [article for _, article in scored[:limit]]
