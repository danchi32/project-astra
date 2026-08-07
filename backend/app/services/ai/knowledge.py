import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle, KnowledgeSource, User
from app.models.base import utcnow
from app.repositories.knowledge import KnowledgeRepository
from app.services.ai import learning
from app.services.ai.aliases import AliasGenerator, embedding_text
from app.services.ai.embeddings import EmbeddingProvider, cosine_similarity, get_embedding_provider
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    def __init__(
        self,
        session: AsyncSession,
        provider: EmbeddingProvider | None = None,
        aliases: AliasGenerator | None = None,
    ) -> None:
        self.session = session
        self.repo = KnowledgeRepository(session)
        self.embed = provider or get_embedding_provider()
        self.aliases = aliases or AliasGenerator()

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        title: str,
        content: str,
        source: KnowledgeSource = KnowledgeSource.MANUAL,
        actor_user_id: uuid.UUID | None = None,
    ) -> KnowledgeArticle:
        # The words a user would type for this, so retrieval has something to match on.
        # Generated once, here, because articles are written rarely and searched constantly.
        aliases = await self.aliases.for_article(title=title, content=content)
        vector = await self.embed.embed(
            embedding_text(title, content, aliases), purpose="document"
        )
        article = await self.repo.add(
            KnowledgeArticle(
                org_id=org_id, title=title, content=content, embedding=vector,
                embedding_model=self.embed.name, symptom_samples=aliases or None,
                source=source, created_by_user_id=actor_user_id,
                # A person wrote this and meant it — it is searchable at once. Only the
                # learned path has to earn its way in.
                published_at=utcnow(),
            )
        )
        await self.session.commit()
        return article

    async def list_for_org(self, *, org_id: uuid.UUID) -> list[KnowledgeArticle]:
        return await self.repo.list_by_org(org_id)

    async def list_page(
        self, *, org_id: uuid.UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[KnowledgeArticle], int]:
        from sqlalchemy import select

        from app.schemas.pagination import paginate

        stmt = (
            select(KnowledgeArticle)
            .where(KnowledgeArticle.org_id == org_id)
            .order_by(KnowledgeArticle.created_at.desc())
        )
        rows, total, _, _ = await paginate(
            self.session, stmt, page=offset // max(1, limit) + 1, page_size=limit
        )
        return rows, total

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
        aliases = await self.aliases.for_article(title=title, content=content)
        vector = await self.embed.embed(
            embedding_text(title, content, aliases), purpose="document"
        )
        article = await self.repo.add(
            KnowledgeArticle(
                org_id=None, title=title, content=content, embedding=vector,
                embedding_model=self.embed.name, symptom_samples=aliases or None,
                source=KnowledgeSource.MANUAL, created_by_user_id=actor_user_id,
                published_at=utcnow(),
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
        every organization.

        Learned articles that have not been confirmed enough times, or whose success rate
        has since collapsed, are not returned. They still exist and staff can still see
        them; they are just not presented to a user as an answer.
        """
        query_vec = await self.embed.embed(query, purpose="query")
        candidates = await self.repo.list_by_org(org_id)
        candidates += await self.repo.list_global()
        candidates = [
            a for a in candidates
            if a.published_at is not None and learning.is_recommendable(a)
        ]

        # Only score articles from this provider's vector space. A vector from another
        # model isn't a weak match, it's an incomparable one — and cosine similarity
        # reports that as 0.0, so without this filter the results would look merely
        # unlucky rather than wrong.
        usable = [a for a in candidates if a.embedding_model == self.embed.name]
        stale = len(candidates) - len(usable)
        if stale:
            # Loud, because the symptom otherwise is "the knowledge base seems empty" and
            # the cause is a provider change nobody connected to it. scripts/reembed.py.
            logger.warning(
                "%s knowledge article(s) are embedded with a different model than the "
                "configured provider (%s) and were skipped — run scripts/reembed.py",
                stale, self.embed.name,
            )

        scored = [(cosine_similarity(query_vec, a.embedding), a) for a in usable]
        # Keep only somewhat-relevant matches, best first.
        scored = [pair for pair in scored if pair[0] > 0.2]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [article for _, article in scored[:limit]]

    # -- Learning from confirmed fixes -----------------------------------------

    async def learn_from_fix(
        self,
        *,
        org_id: uuid.UUID,
        action_id: str,
        action_label: str,
        params: dict | None,
        symptom: str,
        success: bool,
    ) -> KnowledgeArticle | None:
        """Fold one executed fix into the org's knowledge.

        Called on the agent's result path, so it must never be the reason a result fails
        to record: it returns None rather than raising when there is nothing worth
        learning. Does NOT commit — the caller owns the transaction that also writes the
        task result, so a fix and what was learned from it land together or not at all.
        """
        symptom = learning.redact(symptom or "").strip()
        key = learning.topic_key(action_id, params)

        existing = await self.repo.get_learned(org_id=org_id, action_id=key)

        if existing is None:
            # Nothing to learn from a first-ever failure: there is no confirmed fix here,
            # only an attempt that didn't work.
            if not success or not symptom:
                return None
            title, content = learning.render(
                action_label=action_label, samples=[symptom],
                successes=1, failures=0, last_seen=utcnow(),
            )
            return await self.repo.add(
                KnowledgeArticle(
                    org_id=org_id, title=title, content=content,
                    embedding=await self.embed.embed(f"{title}\n{content}",
                                                     purpose="document"),
                    embedding_model=self.embed.name,
                    source=KnowledgeSource.RESOLVED_ISSUE,
                    action_id=key, symptom_samples=[symptom],
                    successes=1, failures=0,
                    published_at=None,  # a candidate until it repeats
                )
            )

        if success:
            existing.successes += 1
        else:
            existing.failures += 1

        samples = list(existing.symptom_samples or [])
        # Only successes contribute vocabulary. A phrasing this fix did NOT resolve is
        # precisely the wording that should not pull this article up next time.
        if success and symptom and symptom.lower() not in {s.lower() for s in samples}:
            samples.append(symptom)
            samples = samples[-learning.MAX_SAMPLES:]

        title, content = learning.render(
            action_label=action_label, samples=samples or [action_label],
            successes=existing.successes, failures=existing.failures, last_seen=utcnow(),
        )
        existing.title = title
        existing.content = content
        existing.symptom_samples = samples
        existing.embedding = await self.embed.embed(f"{title}\n{content}",
                                                    purpose="document")
        existing.embedding_model = self.embed.name

        if existing.published_at is None and existing.successes >= learning.PUBLISH_AFTER:
            existing.published_at = utcnow()

        return existing
