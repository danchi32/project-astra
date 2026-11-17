"""Phase 3 · D7: approvals. A person whose paste or upload SAVIO held asks IT to let it through.

An approval is narrow by design: one Windows account, on one PC, on one site, for one channel
(paste / drop / file / submit), for a limited time (30 minutes unless the admin picks
otherwise, at most 8 hours). It is not an exemption from AI Guard. Admins decide, and every
decision is audited. The agent fetches what is in force for its PC every minute.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, GuardApproval, NotificationCategory, NotificationSeverity, User
from app.models.base import as_utc, utcnow
from app.services.audit import AuditService
from app.services.browser_policy import entitled
from app.services.notifications import NotificationService

PENDING_FOR = timedelta(days=1)
DEFAULT_MINUTES = 30
MIN_MINUTES = 5
MAX_MINUTES = 480


class ApprovalNotFound(LookupError):
    pass


class ApprovalClosed(ValueError):
    """Already decided, or waited too long to be approved now."""


def status_of(a: GuardApproval) -> str:
    """What to show: a pending request past a day is expired, an approval past its time is over."""
    now = utcnow()
    if a.status == "pending" and as_utc(a.requested_at) < now - PENDING_FOR:
        return "expired"
    if a.status == "approved" and a.valid_until and as_utc(a.valid_until) < now:
        return "ended"
    return a.status


async def request(session: AsyncSession, device: Device, e) -> GuardApproval:
    """From an event with action "approve" and outcome "requested". A second request for the
    same thing while one is pending refreshes it instead of piling up."""
    now = utcnow()
    open_ = (await session.execute(select(GuardApproval).where(
        GuardApproval.device_id == device.id, GuardApproval.windows_user == e.windows_user,
        GuardApproval.site == e.site, GuardApproval.channel == e.channel,
        GuardApproval.status == "pending", GuardApproval.requested_at >= now - PENDING_FOR,
    ))).scalars().first()
    if open_ is not None:
        open_.counts, open_.contact_list, open_.keyword_hits = e.counts, e.contact_list, e.keyword_hits
        open_.requested_at = now
        return open_
    a = GuardApproval(org_id=device.org_id, device_id=device.id, windows_user=e.windows_user, site=e.site,
                      channel=e.channel, counts=e.counts, contact_list=e.contact_list,
                      keyword_hits=e.keyword_hits, status="pending", requested_at=now)
    session.add(a)
    await NotificationService(session).notify(
        org_id=device.org_id, category=NotificationCategory.SYSTEM, severity=NotificationSeverity.INFO,
        title="Approval requested",
        message=f"{e.windows_user} on {device.hostname} asks to {_verb(e.channel)} on {e.site}.",
        link="/guard/approvals",
    )
    return a


def _verb(channel: str) -> str:
    return {"paste": "paste", "drop": "drop content", "file": "upload a file", "submit": "send a form"}.get(channel, channel)


async def list_for_org(session: AsyncSession, org_id, limit: int = 200) -> list[tuple[GuardApproval, str]]:
    return list((await session.execute(
        select(GuardApproval, Device.hostname)
        .join(Device, Device.id == GuardApproval.device_id)
        .where(GuardApproval.org_id == org_id)
        .order_by(GuardApproval.requested_at.desc())
        .limit(limit)
    )).all())


async def decide(session: AsyncSession, *, actor: User, approval_id: uuid.UUID, approve: bool,
                 minutes: int = DEFAULT_MINUTES) -> GuardApproval:
    a = await session.get(GuardApproval, approval_id)
    if a is None or a.org_id != actor.org_id:
        raise ApprovalNotFound()
    if status_of(a) != "pending":
        raise ApprovalClosed(f"This request is {status_of(a)}.")
    now = utcnow()
    a.status = "approved" if approve else "denied"
    a.decided_by_user_id, a.decided_at = actor.id, now
    a.valid_until = now + timedelta(minutes=minutes) if approve else None
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id,
        action="guard.approval_approve" if approve else "guard.approval_deny",
        target_type="device", target_id=str(a.device_id),
        detail={"approval": str(a.id), "windows_user": a.windows_user, "site": a.site, "channel": a.channel,
                **({"minutes": minutes} if approve else {})},
    )
    await session.commit()
    return a


async def for_device(session: AsyncSession, device: Device) -> list[dict]:
    """What is in force on this PC now. Nothing without the add-on."""
    if not await entitled(session, device.org_id):
        return []
    now = utcnow()
    rows = (await session.execute(select(GuardApproval).where(
        GuardApproval.device_id == device.id, GuardApproval.status == "approved",
        GuardApproval.valid_until > now,
    ))).scalars().all()
    # Always with its zone: the agent compares it with its own UTC clock.
    return [{"windows_user": a.windows_user, "site": a.site, "channel": a.channel, "valid_until": as_utc(a.valid_until)}
            for a in rows]
