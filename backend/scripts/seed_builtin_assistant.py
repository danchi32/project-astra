"""Seed the built-in ASTRA System Administrator assistant from the live constants.

The prompt is NOT copied into the Alembic migration. It lives in one place —
`app/services/ai/prompts.WINDOWS_EXPERT_PROMPT` — and a migration that duplicated it would
become a second, silently stale copy the first time the prompt is tuned.

Idempotent: re-running updates the built-in row's published version to whatever the
constants currently say, and creates nothing twice. Safe to run on every deploy.

OPTIONAL. Nothing depends on this having run: with no seeded row the engine falls back to
the same constants, which is exactly today's behaviour. Run it when you want the row-driven
path, not because something is broken without it.

PRODUCTION RUNS THIS AUTOMATICALLY. `.github/workflows/deploy-backend.yml` executes it as
the `astra-seed-assistant` Cloud Run job on every backend deploy, after the health gate —
so the connection string stays in Secret Manager and never reaches a laptop, and a broken
seed can never block a deploy that carries real code. You do not need to run it by hand.

To run it locally you must name a target, because `backend/.env` carries no database URL
(production's lives in Secret Manager). Run from anywhere; the chdir above handles the rest:

    ASTRA_DATABASE_URL=sqlite+aiosqlite:///./astra-demo.db \
        backend/.venv/Scripts/python.exe backend/scripts/seed_builtin_assistant.py
"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
# Settings reads `.env` relative to the CURRENT WORKING DIRECTORY, and the app only ever
# resolves it because uvicorn is started from backend/. Run from the repo root — which is
# how the command in this docstring reads — and the file is simply not found, so the script
# dies on "No database URL found" with a perfectly good .env sitting one directory away.
os.chdir(BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Assistant, AssistantVersion, AssistantVersionStatus  # noqa: E402
from app.services.ai.prompts import WINDOWS_EXPERT_PROMPT  # noqa: E402

NAME = "ASTRA System Administrator"
DESCRIPTION = (
    "The built-in IT operations assistant: diagnoses Windows devices from telemetry and "
    "event logs, and proposes fixes within the platform's approval tiers."
)


async def main() -> None:
    async with SessionLocal() as session:
        assistant = await session.scalar(
            select(Assistant).where(Assistant.org_id.is_(None), Assistant.name == NAME)
        )
        if assistant is None:
            assistant = Assistant(org_id=None, name=NAME, description=DESCRIPTION)
            session.add(assistant)
            await session.flush()
            print(f"created assistant {assistant.id}")

        published = None
        if assistant.published_version_id:
            published = await session.get(AssistantVersion, assistant.published_version_id)

        if published is not None and published.system_prompt == WINDOWS_EXPERT_PROMPT:
            print("already current — nothing to do")
            return

        # Model, token and iteration limits stay NULL: NULL means "server default", which is
        # exactly today's behaviour. tool_ids stays NULL for the same reason — the built-in
        # assistant gets whatever the engine advertises, unrestricted.
        next_no = (published.version_no + 1) if published else 1
        version = AssistantVersion(
            assistant_id=assistant.id,
            version_no=next_no,
            status=AssistantVersionStatus.PUBLISHED,
            system_prompt=WINDOWS_EXPERT_PROMPT,
            notes="Seeded from app.services.ai.prompts.WINDOWS_EXPERT_PROMPT",
        )
        session.add(version)
        await session.flush()

        if published is not None:
            published.status = AssistantVersionStatus.ARCHIVED
        assistant.published_version_id = version.id
        await session.commit()
        print(f"published v{next_no} ({version.id})")


if __name__ == "__main__":
    asyncio.run(main())
