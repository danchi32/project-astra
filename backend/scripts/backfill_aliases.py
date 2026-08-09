"""Generate query aliases for knowledge articles that were saved without them.

    python scripts/backfill_aliases.py --dry-run    # how many are affected
    python scripts/backfill_aliases.py              # fix them

An article saved while the LLM was unreachable — or on a deployment with no
ASTRA_ANTHROPIC_API_KEY — has no aliases, and retrieval is lexical: a user typing "wifi"
scores exactly 0.0 against an article titled "Wi-Fi keeps dropping", so the search returns
nothing rather than something imperfect. Nothing retried those articles, so run this after
any period where the model was down.

A thin CLI. The logic lives in app/services/ai/backfill_aliases.py so it is covered by the
test suite.

Safe to re-run and safe to interrupt: each batch commits on its own, articles that already
have aliases are skipped, and an article the model still cannot answer for is left NULL so
the next run picks it up again.
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.services.ai.backfill_aliases import backfill  # noqa: E402
from app.services.ai.embeddings import get_embedding_provider  # noqa: E402


async def main(dry_run: bool) -> int:
    report = await backfill(SessionLocal, get_embedding_provider(), dry_run=dry_run)
    for line in report.lines():
        print(line, flush=True)
    return 1 if report.error else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report how many articles are missing aliases, and stop",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
