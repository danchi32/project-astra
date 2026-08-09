"""Filling in query aliases for articles that were saved without them.

`AliasGenerator.for_article` never raises — an article must save even when the model is
down — so a write during an LLM outage, or on a deployment with no key configured, stores
the article with no aliases and `aliases_generated_at` left NULL.

That is not cosmetic. Retrieval is lexical: an article titled "Wi-Fi keeps dropping"
tokenises to `['wi','fi',...]`, a user types `wifi`, the two share nothing, and cosine
similarity is exactly 0.0 — below the 0.2 floor, so the search returns *nothing at all*.
Measured, not assumed: the same article with aliases scores 0.612 for the same query.

Nothing retried those articles and nothing counted them, so the failure was permanent and
invisible. This is the retry. Same shape as `reembed` deliberately — one place to look for
"the vectors need rebuilding", one for "the aliases were never written".
"""
import logging
from dataclasses import dataclass

from sqlalchemy import func, select

from app.models import KnowledgeArticle
from app.models.base import utcnow
from app.services.ai.aliases import AliasGenerator, embedding_text
from app.services.ai.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

BATCH = 25


@dataclass
class Report:
    dry_run: bool
    missing: int = 0
    filled: int = 0
    still_missing: int = 0
    error: str | None = None

    def lines(self) -> list[str]:
        if self.error:
            return [f"Alias backfill aborted: {self.error}"]
        out = [f"Articles with no aliases: {self.missing}"]
        if self.dry_run:
            out.append("Dry run — nothing was written.")
            return out
        out.append(f"Aliases generated for: {self.filled}")
        if self.still_missing:
            out.append(
                f"Still without aliases: {self.still_missing} — the model declined or was "
                "unavailable for these. Safe to re-run."
            )
        return out


async def backfill(session_factory, provider: EmbeddingProvider, *, dry_run: bool = False) -> Report:
    """Generate aliases for every article missing them, and re-embed those articles.

    Re-embedding is not optional: the aliases only help retrieval because they are part of
    the embedded text. Writing them to the column without rebuilding the vector would look
    like it worked and change nothing.
    """
    report = Report(dry_run=dry_run)
    generator = AliasGenerator()

    async with session_factory() as session:
        report.missing = int((await session.execute(
            select(func.count()).select_from(KnowledgeArticle)
            .where(KnowledgeArticle.aliases_generated_at.is_(None))
        )).scalar_one())

    if dry_run or not report.missing:
        return report

    while True:
        async with session_factory() as session:
            rows = list((await session.execute(
                select(KnowledgeArticle)
                .where(KnowledgeArticle.aliases_generated_at.is_(None))
                .limit(BATCH)
            )).scalars().all())
            if not rows:
                break

            progressed = False
            for article in rows:
                aliases = await generator.for_article(
                    title=article.title, content=article.content
                )
                if aliases is None:
                    # Still unavailable. Left NULL on purpose so a later run picks it up
                    # again — writing [] here would mark it "done" and make it permanent.
                    report.still_missing += 1
                    continue
                article.symptom_samples = aliases
                article.aliases_generated_at = utcnow()
                article.embedding = await provider.embed(
                    embedding_text(article.title, article.content, aliases),
                    purpose="document",
                )
                article.embedding_model = provider.name
                report.filled += 1
                progressed = True

            await session.commit()

            if not progressed:
                # Every article in this batch failed, so the next batch would be the same
                # rows forever. The model is down; stop and let the operator re-run.
                logger.warning(
                    "Alias backfill made no progress — the model is unavailable. "
                    "%s article(s) still have no aliases.", report.still_missing,
                )
                break

    return report
