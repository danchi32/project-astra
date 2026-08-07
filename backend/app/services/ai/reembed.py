"""Rebuilding stored vectors after the embedding vector space changes.

Lives here rather than in the script so it can be tested. The first version of this was a
standalone file under scripts/, which meant nothing executed it until it ran against
production — where it failed on its very first import. A migration tool that has never
been run is not a tool, it is a plan.

Switching provider, model, or tokenizer changes the space. Existing rows keep their old
vectors and are correctly excluded from search — nothing returns a wrong answer — but they
stay invisible until rebuilt.
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select

from app.models import KnowledgeArticle, LearnedAction, SemanticCacheEntry
from app.services.ai.embeddings import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)

BATCH = 50

# (model, human label, how to rebuild the text that gets embedded)
TARGETS = [
    (KnowledgeArticle, "knowledge articles",
     lambda r: "\n".join([r.title, r.content, *(r.symptom_samples or [])])),
    (SemanticCacheEntry, "cached answers", lambda r: r.query_text),
    (LearnedAction, "learned fixes", lambda r: r.query_text),
]


@dataclass
class Report:
    provider: str
    dry_run: bool
    stale: dict[str, int] = field(default_factory=dict)
    done: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def total_stale(self) -> int:
        return sum(self.stale.values())

    @property
    def total_done(self) -> int:
        return sum(self.done.values())

    def lines(self) -> list[str]:
        out = [f"Configured embedding provider: {self.provider}", ""]
        for label, count in self.stale.items():
            if count == 0:
                out.append(f"  {label}: up to date")
            elif self.dry_run:
                out.append(f"  {label}: {count} row(s) would be re-embedded")
            else:
                out.append(f"  {label}: {self.done.get(label, 0)}/{count} re-embedded")
        out.append("")
        if self.dry_run:
            out.append(f"Dry run: {self.total_stale} row(s) would be re-embedded. "
                       f"Nothing changed.")
        elif self.error:
            out.append(f"Stopped after an embedding failure: {self.error}")
            out.append(f"Re-embedded {self.total_done} row(s) before stopping; the rest "
                       f"keep their previous vectors. Fix the provider and re-run.")
        else:
            out.append(f"Re-embedded {self.total_done} row(s) onto {self.provider}.")
        return out


async def reembed_all(session_factory, provider: EmbeddingProvider, *,
                      dry_run: bool = True) -> Report:
    """Rebuild every vector not already on `provider`.

    Commits per batch and skips rows already current, so an interrupted run resumes rather
    than repeats. Stops at the first embedding failure — if the service is refusing,
    grinding through the remainder just repeats it — leaving those rows on their previous
    vectors, which is the state they were already in.
    """
    report = Report(provider=provider.name, dry_run=dry_run)

    for model, label, text_of in TARGETS:
        async with session_factory() as session:
            stale = int((await session.execute(
                select(func.count()).select_from(model)
                .where(model.embedding_model != provider.name)
            )).scalar_one())
        report.stale[label] = stale
        if stale == 0 or dry_run:
            continue

        done = 0
        while done < stale:
            async with session_factory() as session:
                rows = list((await session.execute(
                    select(model)
                    .where(model.embedding_model != provider.name)
                    .limit(BATCH)
                )).scalars())
                if not rows:
                    break
                for row in rows:
                    try:
                        row.embedding = await provider.embed(text_of(row), purpose="document")
                        row.embedding_model = provider.name
                        done += 1
                    except EmbeddingError as exc:
                        await session.commit()
                        report.done[label] = done
                        report.error = str(exc)
                        return report
                await session.commit()
        report.done[label] = done

    return report
