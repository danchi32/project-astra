"""Re-embed stored vectors after an embedding provider, model, or tokenizer change.

    python scripts/reembed.py --dry-run     # what would change, and how much of it
    python scripts/reembed.py               # do it

A thin CLI. The logic lives in app/services/ai/reembed.py so it is covered by the test
suite — the first version of this was a standalone script, which meant nothing ran it
until production did, where it failed on its first import.

Safe to re-run and safe to interrupt: each batch commits on its own and rows already on
the current model are skipped, so a second run resumes rather than repeats.
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.services.ai.embeddings import get_embedding_provider  # noqa: E402
from app.services.ai.reembed import reembed_all  # noqa: E402


async def main(dry_run: bool) -> int:
    report = await reembed_all(SessionLocal, get_embedding_provider(), dry_run=dry_run)
    for line in report.lines():
        print(line, flush=True)
    return 1 if report.error else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would be re-embedded, and stop",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
