"""Re-embed stored vectors after an embedding provider or model change.

Switching provider changes the vector space. Existing rows keep their old vectors and are
correctly excluded from search — nothing returns a wrong answer — but they stay invisible
until re-embedded. This walks the three embedding-backed tables and rebuilds anything not
already on the configured provider.

    python scripts/reembed.py --dry-run     # what would change, and how much of it
    python scripts/reembed.py               # do it

Safe to re-run and safe to interrupt: each batch commits on its own and rows already on the
current model are skipped, so a second run resumes rather than repeats.

Cost note: every stale row is sent to the embedding API. --dry-run reports the count first
so that isn't a surprise on a large knowledge base.
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import func, select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models import KnowledgeArticle, LearnedAction, SemanticCacheEntry  # noqa: E402
from app.services.ai.embeddings import EmbeddingError, get_embedding_provider  # noqa: E402

# (model, human label, how to build the text that gets embedded)
TARGETS = [
    (KnowledgeArticle, "knowledge articles", lambda r: f"{r.title}\n{r.content}"),
    (SemanticCacheEntry, "cached answers", lambda r: r.query_text),
    (LearnedAction, "learned fixes", lambda r: r.query_text),
]

BATCH = 50


async def _count_stale(session, model, provider_name: str) -> int:
    stmt = (
        select(func.count())
        .select_from(model)
        .where(model.embedding_model != provider_name)
    )
    return int((await session.execute(stmt)).scalar_one())


async def _reembed_table(provider, model, label, text_of, stale: int) -> tuple[int, str | None]:
    """Returns (rows done, first error). Stops at the first failure — if the embedding
    service is refusing, grinding through the rest just repeats the failure."""
    done = 0
    while done < stale:
        async with async_session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(model)
                        .where(model.embedding_model != provider.name)
                        .limit(BATCH)
                    )
                ).scalars()
            )
            if not rows:
                break
            for row in rows:
                try:
                    row.embedding = await provider.embed(text_of(row), purpose="document")
                    row.embedding_model = provider.name
                    done += 1
                except EmbeddingError as exc:
                    # Commit what already succeeded, then stop. The failed row keeps its
                    # previous vector — the same state it was in before this run — and the
                    # next run picks it up again.
                    await session.commit()
                    return done, str(exc)
            await session.commit()
        print(f"    {done}/{stale}", end="\r", flush=True)
    print(f"    {done}/{stale} done      ")
    return done, None


async def run(dry_run: bool) -> int:
    provider = get_embedding_provider()
    print(f"Configured embedding provider: {provider.name}\n")

    total_stale = 0
    total_done = 0
    first_error: str | None = None

    for model, label, text_of in TARGETS:
        async with async_session_factory() as session:
            stale = await _count_stale(session, model, provider.name)
        total_stale += stale

        if stale == 0:
            print(f"  {label}: up to date")
            continue
        if dry_run:
            print(f"  {label}: {stale} row(s) would be re-embedded")
            continue

        print(f"  {label}: re-embedding {stale} row(s)…")
        done, error = await _reembed_table(provider, model, label, text_of, stale)
        total_done += done
        if error:
            first_error = error
            break

    print()
    if dry_run:
        print(f"Dry run: {total_stale} row(s) would be re-embedded. Nothing changed.")
        return 0
    if first_error:
        print(f"Stopped after an embedding failure: {first_error}")
        print(f"Re-embedded {total_done} row(s) before stopping; the rest keep their "
              f"previous vectors. Fix the provider and re-run to continue.")
        return 1
    print(f"Re-embedded {total_done} row(s) onto {provider.name}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would be re-embedded, and stop",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.dry_run)))
