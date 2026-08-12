"""Turning what ASTRA tried in a conversation into the dossier a technician reads.

Two paths now escalate: a fix that failed on the machine, and a user who says the fix made
no difference. They describe the same situation and must describe it the same way, so the
building lives here rather than being written out twice — the last two times a fact was
stated in two places in this codebase, the two copies disagreed.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Message, MessageRole, RemediationTask
from app.models.remediation import RemediationStatus
from app.services.remediation.actions import get_action
from app.services.support.dossier import Attempt, Dossier


async def attempts_in(
    session: AsyncSession, conversation_id: uuid.UUID
) -> list[RemediationTask]:
    """Every fix ASTRA started in this conversation, oldest first."""
    return list((await session.execute(
        select(RemediationTask)
        .where(RemediationTask.conversation_id == conversation_id)
        .order_by(RemediationTask.created_at.asc())
    )).scalars().all())


async def first_complaint(
    session: AsyncSession, conversation_id: uuid.UUID
) -> str | None:
    """The user's opening words. Not the latest message: by the time somebody says "still
    not working", the sentence that describes the actual problem is further up."""
    return (await session.execute(
        select(Message.content).where(
            Message.conversation_id == conversation_id,
            Message.role == MessageRole.USER,
        ).order_by(Message.created_at.asc()).limit(1)
    )).scalar_one_or_none()


async def complaint_before(
    session: AsyncSession, conversation_id: uuid.UUID, moment: datetime
) -> str | None:
    """The last thing the user said before `moment` — what a fix started then was answering.

    Different from `first_complaint` on purpose: a chat that raised two problems in turn has
    two complaints, and a fix belongs to the nearer one.
    """
    return (await session.execute(
        select(Message.content).where(
            Message.conversation_id == conversation_id,
            Message.role == MessageRole.USER,
            Message.created_at <= moment,
        ).order_by(Message.created_at.desc()).limit(1)
    )).scalar_one_or_none()


def _attempt_of(task: RemediationTask) -> Attempt:
    action = get_action(task.action_id)
    label = action.label if action else task.action_id
    return Attempt(
        label=label,
        succeeded=task.status is RemediationStatus.SUCCEEDED,
        outcome=(task.result or {}).get("output", "")[:200] or None,
        at=task.completed_at,
    )


async def build_dossier(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    device_id: uuid.UUID | None,
    problem: str | None = None,
) -> Dossier | None:
    """The evidence for one escalation, or None when there is no complaint to attach it to.

    Every attempt in the conversation goes in, not only the last one: a technician picking
    this up needs to know what has already been ruled out, or the first thing they do is
    the thing that already failed.
    """
    complaint = problem or await first_complaint(session, conversation_id)
    if not complaint:
        return None

    device = await session.get(Device, device_id) if device_id else None
    attempts = [_attempt_of(t) for t in await attempts_in(session, conversation_id)]

    return Dossier(
        problem=complaint[:1000],
        hostname=device.hostname if device else None,
        os_version=device.os_version if device else None,
        attempts=attempts,
    )
