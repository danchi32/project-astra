"""SAVIO support access — the customer, not SAVIO, decides when we may look.

A platform admin can open a read-only "view as" session on a customer's portal. That used to
need nothing from the customer; it was audited under their org, but never asked. Now the
customer's admin opens a time-boxed window (1, 24 or 72 hours) from Settings, can close it at
any time, and every view-as token is refused — at minting AND on every request — unless the
window is open. Closing the window ends an open session on its next request, not when its
token happens to expire.

Demo organisations (``is_demo``, our own sales tenants) are exempt: there is no customer to ask.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User
from app.models.base import as_utc, utcnow
from app.models.notification import NotificationCategory, NotificationSeverity
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError
from app.services.notifications import NotificationService

#: The only windows a customer can grant. Short on purpose: access that is never revoked
#: should still end on its own.
ALLOWED_HOURS = (1, 24, 72)


def window_open(org: Organization, now: datetime | None = None) -> bool:
    if org.is_demo:
        return True
    until = org.support_access_until
    return until is not None and as_utc(until) > (now or utcnow())


def remaining_minutes(org: Organization) -> int:
    """Minutes left in the window (60 for a demo org); 0 when closed."""
    if org.is_demo:
        return 60
    if not window_open(org):
        return 0
    return max(1, int((as_utc(org.support_access_until) - utcnow()).total_seconds() // 60))


class SupportAccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def _org(self, org_id) -> Organization:
        org = await self.session.get(Organization, org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        return org

    async def get(self, *, actor: User) -> Organization:
        return await self._org(actor.org_id)

    async def grant(self, *, actor: User, hours: int) -> Organization:
        org = await self._org(actor.org_id)
        org.support_access_until = utcnow() + timedelta(hours=hours)
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="support_access.grant",
            target_type="organization", target_id=str(org.id),
            detail={"hours": hours, "until": org.support_access_until.isoformat()},
        )
        await self.session.commit()
        return org

    async def revoke(self, *, actor: User) -> Organization:
        org = await self._org(actor.org_id)
        org.support_access_until = None
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="support_access.revoke",
            target_type="organization", target_id=str(org.id), detail={},
        )
        await self.session.commit()
        return org

    async def request(self, *, actor: User, org_id, reason: str) -> None:
        """A platform admin asks the customer to open the window. Notifies the org's admins
        and leaves an audit entry in THEIR log, so the ask itself is visible to them."""
        org = await self._org(org_id)
        await NotificationService(self.session).notify(
            org_id=org.id,
            category=NotificationCategory.SYSTEM,
            severity=NotificationSeverity.INFO,
            title="SAVIO support is asking for access",
            message=(f"{actor.full_name or actor.email} from SAVIO support asks to view your "
                     f"portal (read-only): {reason}. Grant it in Settings → Support access."),
            link="/settings",
        )
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="support_access.request",
            target_type="organization", target_id=str(org.id), detail={"reason": reason, "by": actor.email},
        )
        await self.session.commit()
