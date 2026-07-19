"""Per-organization outbound email identity (DNS-verified sending).

An org sets the address it wants ASTRA to send as (e.g. it-support@acme.com); we register
that domain with Resend, hand back the DNS records to publish, and — once verified — send
customer-facing mail (asset acknowledgements, etc.) AS the org. Designed so the OAuth methods
can slot in later behind the same `resolve_sender` entry point.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailSettings, EmailVerificationStatus, User
from app.models.base import utcnow
from app.services import email_domains
from app.services.audit import AuditService
from app.services.email_domains import EmailProviderError

_EMAIL_RE = re.compile(r"^[^@\s]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})$")


@dataclass(frozen=True)
class OrgSender:
    """The verified identity ASTRA sends as for one org."""
    from_name: str | None
    from_address: str


class EmailIntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def _row(self, org_id: uuid.UUID) -> EmailSettings | None:
        return (await self.session.execute(
            select(EmailSettings).where(EmailSettings.org_id == org_id)
        )).scalar_one_or_none()

    async def read(self, *, org_id: uuid.UUID) -> EmailSettings | None:
        return await self._row(org_id)

    async def configure(
        self, *, actor: User, from_name: str, from_address: str
    ) -> EmailSettings:
        """Set the org's sending address and register its domain with the provider,
        returning the row with the DNS records the org must publish."""
        from_address = from_address.strip().lower()
        m = _EMAIL_RE.match(from_address)
        if m is None:
            raise ValueError("Enter a valid email address, e.g. it-support@yourcompany.com")
        domain = m.group(1)

        row = await self._row(actor.org_id)
        if row is None:
            row = EmailSettings(org_id=actor.org_id)
            self.session.add(row)

        row.from_name = from_name.strip() or None
        row.from_address = from_address
        row.last_error = None

        try:
            # Reuse the provider domain when it's unchanged; otherwise (re)register it.
            if row.domain == domain and row.provider_domain_id:
                payload = await email_domains.get_domain(row.provider_domain_id)
            else:
                payload = await email_domains.create_domain(domain)
                row.provider_domain_id = str(payload.get("id") or "")
            row.domain = domain
            row.dns_records = email_domains.normalize_records(payload)
            row.status = _status_from_payload(payload)
        except EmailProviderError as exc:
            row.status = EmailVerificationStatus.FAILED
            row.last_error = str(exc)[:500]
            await self.audit.record(
                org_id=actor.org_id, actor_id=actor.id, action="email.configure_failed",
                target_type="email_settings", target_id=domain, detail={"error": row.last_error},
            )
            await self.session.commit()
            raise

        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="email.configure",
            target_type="email_settings", target_id=domain,
            detail={"from_address": from_address},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def verify(self, *, actor: User) -> EmailSettings:
        """Trigger a DNS re-check with the provider and update our stored status."""
        row = await self._row(actor.org_id)
        if row is None or not row.provider_domain_id:
            raise ValueError("Set a sending address first.")
        try:
            await email_domains.verify_domain(row.provider_domain_id)
            payload = await email_domains.get_domain(row.provider_domain_id)
        except EmailProviderError as exc:
            row.last_error = str(exc)[:500]
            await self.session.commit()
            raise

        row.dns_records = email_domains.normalize_records(payload)
        row.status = _status_from_payload(payload)
        row.last_error = None
        if row.status is EmailVerificationStatus.VERIFIED and row.verified_at is None:
            row.verified_at = utcnow()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="email.verify",
            target_type="email_settings", target_id=row.domain or "",
            detail={"status": row.status.value},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return row

    @staticmethod
    async def resolve_sender(session: AsyncSession, org_id: uuid.UUID) -> OrgSender | None:
        """The verified identity to send an org's mail as, or None to use ASTRA's default.
        This is the single seam OAuth methods will also implement later."""
        row = (await session.execute(
            select(EmailSettings).where(EmailSettings.org_id == org_id)
        )).scalar_one_or_none()
        if row and row.status is EmailVerificationStatus.VERIFIED and row.from_address:
            return OrgSender(from_name=row.from_name, from_address=row.from_address)
        return None


def _status_from_payload(payload: dict) -> EmailVerificationStatus:
    # Resend domain status is one of: not_started, pending, verified, failed, temporary_failure.
    raw = (payload.get("status") or "").lower()
    if raw == "verified":
        return EmailVerificationStatus.VERIFIED
    if raw in ("failed",):
        return EmailVerificationStatus.FAILED
    return EmailVerificationStatus.PENDING
