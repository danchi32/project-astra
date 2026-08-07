"""Working out whose ticket this is.

A ticket filed against the wrong person is worse than no ticket. Their SLA clock runs for
someone who never asked, the CSAT survey goes to a stranger, and the employee who actually
has the problem never hears back about it — while believing help is on the way.

So this resolves an email or it returns None, and None means ASTRA does not offer to raise
a ticket at all. It never invents an address from a username and a domain: a guessed
address either bounces or, worse, creates a plausible-looking contact in the customer's
helpdesk that nobody owns.

Precedence runs from stated to inferred:

  1. The conversation belongs to a portal user — they told us who they are.
  2. The device is an asset assigned to someone — an explicit, human-made assignment.
  3. The Windows logged-in user matches an account in this org — an inference, but a
     narrow one: the local part of an email in the same organization.
"""
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Conversation, Device, User

logger = logging.getLogger(__name__)


@dataclass
class Requester:
    email: str
    user_id: uuid.UUID | None
    how: str          # which rule matched — carried into logs, not into the ticket


async def resolve(
    session: AsyncSession, *, org_id: uuid.UUID, conversation_id: uuid.UUID | None,
    device_id: uuid.UUID | None,
) -> Requester | None:
    if conversation_id is not None:
        convo = await session.get(Conversation, conversation_id)
        if convo is not None:
            if convo.user_id is not None:
                user = await session.get(User, convo.user_id)
                if user is not None and user.email:
                    return Requester(user.email, user.id, "conversation user")
            device_id = device_id or convo.device_id

    if device_id is None:
        return None

    # An asset assignment is a deliberate act by an administrator: this laptop belongs to
    # this person. Better evidence than whoever happens to be signed in right now.
    assigned = (await session.execute(
        select(Asset.assigned_to_user_id)
        .where(Asset.device_id == device_id, Asset.assigned_to_user_id.isnot(None))
        .limit(1)
    )).scalars().first()
    if assigned is not None:
        user = await session.get(User, assigned)
        if user is not None and user.email and user.org_id == org_id:
            return Requester(user.email, user.id, "asset assignment")

    device = await session.get(Device, device_id)
    if device is None or not device.logged_in_user:
        return None

    # "LANCESOFT\\priya.sharma" or "priya.sharma" -> "priya.sharma"
    username = device.logged_in_user.split("\\")[-1].split("/")[-1].strip().lower()
    if not username:
        return None

    # Match within this organization only, and only on the local part of a real address we
    # already hold. This finds an account that exists; it does not manufacture one.
    user = (await session.execute(
        select(User).where(
            User.org_id == org_id,
            func.lower(func.substr(User.email, 1, func.length(User.email))).like(f"{username}@%"),
        ).limit(1)
    )).scalars().first()
    if user is not None:
        return Requester(user.email, user.id, "logged-in user matched to an account")

    logger.info(
        "No requester could be resolved for device %s (logged in as %r) — not offering "
        "to raise a ticket", device_id, device.logged_in_user,
    )
    return None
