"""Seed the built-in ASTRA System Administrator assistant from the live constants.

The prompt is NOT copied into the Alembic migration. It lives in one place —
`app/services/ai/prompts.WINDOWS_EXPERT_PROMPT` — and a migration that duplicated it would
become a second, silently stale copy the first time the prompt is tuned.

Idempotent: re-running updates the built-in row's published version to whatever the
constants currently say, and creates nothing twice. Safe to run on every deploy.

    backend/.venv/Scripts/python.exe backend/scripts/seed_builtin_assistant.py
"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

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
