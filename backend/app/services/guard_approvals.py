"""Phase 3 · D7: approvals. A person whose paste or upload SAVIO held asks IT to let it through.

An approval is narrow by design: one Windows account, on one PC, on one site, for one channel
(paste / drop / file / submit), for a limited time (30 minutes unless the admin picks
otherwise, at most 8 hours). It is not an exemption from AI Guard. Admins decide, and every
decision is audited. The agent fetches what is in force for its PC every minute.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    GuardApproval,
    GuardUsbWindow,
    NotificationCategory,
    NotificationSeverity,
    User,
)
from app.models.base import as_utc, utcnow
from app.services.audit import AuditService
from app.services.browser_policy import entitled
from app.services.notifications import NotificationService

PENDING_FOR = timedelta(days=1)
DEFAULT_MINUTES = 30
MIN_MINUTES = 5
MAX_MINUTES = 480
MAX_PENDING_PER_DEVICE = 20
NOTIFY_EVERY = timedelta(minutes=10)
RETENTION = timedelta(days=180)


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


async def request(session: AsyncSession, device: Device, e) -> GuardApproval | None:
    """From an event with action "approve" and outcome "requested".

    - A second request for the same thing while one is pending refreshes it. If what was found
      changed, its `requested_at` moves, so an admin who looked at the old one must look again
      (see `decide`).
    - A device can hold at most MAX_PENDING_PER_DEVICE open requests; more are ignored, so a
      stolen device token cannot bury real requests.
    - The notification names nobody: notifications reach every role in the org, while who asked
      for what is for admins only (security review H1). At most one per org every 10 minutes."""
    now = utcnow()
    live = (GuardApproval.device_id == device.id, GuardApproval.status == "pending",
            GuardApproval.requested_at >= now - PENDING_FOR)
    open_ = (await session.execute(select(GuardApproval).where(
        *live, GuardApproval.windows_user == e.windows_user,
        GuardApproval.site == e.site, GuardApproval.channel == e.channel,
    ))).scalars().first()
    if open_ is not None:
        if (open_.counts, open_.contact_list, open_.keyword_hits) != (e.counts, e.contact_list, e.keyword_hits):
            open_.counts, open_.contact_list, open_.keyword_hits = e.counts, e.contact_list, e.keyword_hits
            open_.requested_at = now
        return open_
    if (await session.execute(select(func.count()).where(*live))).scalar_one() >= MAX_PENDING_PER_DEVICE:
        return None

    # Retention, per device as for events: decided or expired requests older than half a year go.
    await session.execute(delete(GuardApproval).where(
        GuardApproval.device_id == device.id, GuardApproval.requested_at < now - RETENTION))
    recent = (await session.execute(select(func.count()).where(
        GuardApproval.org_id == device.org_id, GuardApproval.status == "pending",
        GuardApproval.requested_at >= now - NOTIFY_EVERY))).scalar_one()
    a = GuardApproval(org_id=device.org_id, device_id=device.id, windows_user=e.windows_user, site=e.site,
                      channel=e.channel, counts=e.counts, contact_list=e.contact_list,
                      keyword_hits=e.keyword_hits, status="pending", requested_at=now,
                      reason=getattr(e, "usb_reason", None))
    session.add(a)
    if recent == 0:
        what = "USB writing on their PC" if e.channel == "usb" else "a paste or upload"
        await NotificationService(session).notify(
            org_id=device.org_id, category=NotificationCategory.SYSTEM, severity=NotificationSeverity.INFO,
            title="Approval requested",
            message=f"Someone is waiting for IT to approve {what}. An admin can review it under AI Guard.",
            link="/guard/approvals",
        )
    return a


USB_REASONS = ("client_or_ca", "backup", "presentation", "other")


async def request_usb(session: AsyncSession, device: Device, windows_user: str, reason: str) -> GuardApproval | None:
    """C3b: the person at a PC whose USB drives are read-only asks IT for a write window, from
    the tray. The same queue, limits and notification as any approval; approving it opens the
    PC's window (see `decide`)."""
    from types import SimpleNamespace

    e = SimpleNamespace(windows_user=windows_user, site="usb", channel="usb", counts={}, contact_list=False,
                        keyword_hits=0, usb_reason=reason)
    a = await request(session, device, e)
    if a is not None and a.reason != reason:
        a.reason, a.requested_at = reason, utcnow()   # asked again for another reason: look again
    await session.commit()
    return a


async def list_for_org(session: AsyncSession, org_id, limit: int = 200) -> list[tuple[GuardApproval, str]]:
    """Pending first, so a pile of history can never push a waiting request out of view."""
    return list((await session.execute(
        select(GuardApproval, Device.hostname)
        .join(Device, Device.id == GuardApproval.device_id)
        .where(GuardApproval.org_id == org_id)
        .order_by((GuardApproval.status == "pending").desc(), GuardApproval.requested_at.desc())
        .limit(limit)
    )).all())


async def decide(session: AsyncSession, *, actor: User, approval_id: uuid.UUID, approve: bool,
                 seen_requested_at: datetime, minutes: int = DEFAULT_MINUTES) -> GuardApproval:
    """Decide what the admin actually looked at. `seen_requested_at` is the request's time as
    the admin's screen showed it; if the device has since changed what was found, the request
    has a new time and the decision is refused. The update itself only matches a row that is
    still pending with that time, so two admins deciding at once cannot both win."""
    a = await session.get(GuardApproval, approval_id)
    if a is None or a.org_id != actor.org_id:
        raise ApprovalNotFound()
    if status_of(a) != "pending":
        raise ApprovalClosed(f"This request is {status_of(a)}.")
    if as_utc(a.requested_at) != as_utc(seen_requested_at):
        raise ApprovalClosed("This request changed since you looked at it. Review it again.")
    now = utcnow()
    decided = await session.execute(
        update(GuardApproval)
        .where(GuardApproval.id == a.id, GuardApproval.org_id == actor.org_id,
               GuardApproval.status == "pending", GuardApproval.requested_at == a.requested_at)
        .values(status="approved" if approve else "denied", decided_by_user_id=actor.id, decided_at=now,
                valid_until=now + timedelta(minutes=minutes) if approve else None)
        .execution_options(synchronize_session=False)
    )
    if decided.rowcount != 1:
        await session.rollback()
        raise ApprovalClosed("Someone else decided or changed this request a moment ago. Reload to see it.")
    if approve and a.channel == "usb":
        # C3b: a USB request approved is that PC's write window, until the approval ends.
        window = await session.get(GuardUsbWindow, a.device_id)
        if window is None:
            window = GuardUsbWindow(device_id=a.device_id, org_id=a.org_id, until=now)
            session.add(window)
        window.until, window.opened_by_user_id, window.opened_at = now + timedelta(minutes=minutes), actor.id, now
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id,
        action="guard.approval_approve" if approve else "guard.approval_deny",
        target_type="device", target_id=str(a.device_id),
        detail={"approval": str(a.id), "windows_user": a.windows_user, "site": a.site, "channel": a.channel,
                **({"minutes": minutes} if approve else {})},
    )
    await session.commit()
    await session.refresh(a)
    return a


async def for_device(session: AsyncSession, device: Device) -> list[dict]:
    """What is in force on this PC now. Nothing without the add-on."""
    if not await entitled(session, device.org_id):
        return []
    now = utcnow()
    rows = (await session.execute(select(GuardApproval).where(
        GuardApproval.device_id == device.id, GuardApproval.status == "approved",
        GuardApproval.valid_until > now, GuardApproval.channel != "usb",   # USB: the write window instead
    ))).scalars().all()
    # Always with its zone: the agent compares it with its own UTC clock.
    return [{"windows_user": a.windows_user, "site": a.site, "channel": a.channel, "valid_until": as_utc(a.valid_until)}
            for a in rows]
