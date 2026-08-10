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

from app.models import EmailSendMethod, EmailSettings, EmailVerificationStatus, User
from app.models.base import utcnow
from app.services import email_domains
from app.services.audit import AuditService
from app.services.email_domains import EmailProviderError
from app.services.email_templates import sanitize_body

_EMAIL_RE = re.compile(r"^[^@\s]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})$")

#: How many addresses may be copied on an asset email. A cap because this list is applied
#: to every assignment: a fleet handover of two hundred laptops with ten addresses copied
#: is two thousand messages, and a shared mailbox is the right answer past a handful.
MAX_CC = 5


def _clean_cc(addresses: list[str]) -> list[str] | None:
    """Normalise a CC list, or None for empty.

    Invalid entries are dropped rather than rejected: a trailing comma or a stray space in
    a pasted list should not fail the whole save and lose the admin's template edits along
    with it. Order is kept so the list reads back the way it was typed.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in addresses:
        addr = (raw or "").strip().lower()
        if not addr or addr in seen or not _EMAIL_RE.match(addr):
            continue
        seen.add(addr)
        out.append(addr)
        if len(out) >= MAX_CC:
            break
    return out or None


@dataclass(frozen=True)
class OrgSender:
    """Who one org's mail goes out as.

    `from_address` is None for the shared sender: the caller passes None down to
    EmailService, which fills in ASTRA's own configured address. Saying it that way rather
    than resolving our address here keeps one owner for "what is ASTRA's From address".
    """
    from_name: str | None
    from_address: str | None
    reply_to: str | None = None
    #: True when the From address belongs to ASTRA rather than to the organization. The
    #: portal uses it to explain what recipients will see.
    shared: bool = False


class SharedSenderNotEntitled(Exception):
    """The org's plan doesn't include sending from ASTRA's own address."""


class EmailIntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    @staticmethod
    async def shared_sender_allowed(session: AsyncSession, org_id: uuid.UUID) -> bool:
        """Whether this org may send from ASTRA's address.

        Derived from the plan plus the operator's per-org overrides, like every other
        entitlement — so granting an exception is the same one-click act on the org page
        that it is for any other feature, and it is audited the same way.
        """
        from app.models import Organization
        from app.services.entitlements import SHARED_EMAIL_SENDER, features_for

        org = await session.get(Organization, org_id)
        if org is None:
            return False
        return SHARED_EMAIL_SENDER in features_for(org.plan, org.entitlement_overrides)

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
        # Registering your own domain IS choosing it. Without this an admin could complete
        # DNS verification and still have every message go out from ASTRA's address,
        # because `method` was left on the default — which looks exactly like the feature
        # not working, with nothing anywhere saying why.
        row.method = EmailSendMethod.DNS

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

    async def choose_sender(
        self, *, actor: User, method: EmailSendMethod,
        from_name: str | None, reply_to: str | None,
    ) -> EmailSettings:
        """Pick which of the two ways this org's mail goes out.

        Switching to `shared` deliberately leaves the domain rows alone. An org that
        verified acme.com, switched to shared for a week, and switched back should not have
        to redo the DNS — and a verified domain costs nothing to keep sitting there.
        """
        if method is EmailSendMethod.SHARED and not await self.shared_sender_allowed(
            self.session, actor.org_id
        ):
            raise SharedSenderNotEntitled(
                "Sending through ASTRA's address isn't included in your plan. Set up your "
                "own sending domain below, or ask your ASTRA operator to enable it."
            )

        row = await self._row(actor.org_id)
        if row is None:
            row = EmailSettings(org_id=actor.org_id)
            self.session.add(row)

        row.method = method
        if from_name is not None:
            row.from_name = from_name.strip() or None
        row.reply_to = (reply_to or "").strip().lower() or None

        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="email.sender_method",
            target_type="email_settings", target_id=row.domain or "",
            detail={"method": method.value, "reply_to_set": bool(row.reply_to)},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_asset_template(
        self, *, actor: User, subject: str, body: str, cc: list[str] | None = None,
        body_format: str = "text",
    ) -> EmailSettings:
        """Save the org's asset-assignment email template. Blank fields reset to the default
        (stored as NULL). A row is created even before a sending domain is set.

        The body is sanitized on the way in as well as on the way out. Once at render time
        would be enough to keep the mail safe, but storing what the author sent means the
        editor later reloads markup we would refuse to send, and the difference between what
        it shows and what goes out is exactly the confusion this feature keeps producing.
        """
        row = await self._row(actor.org_id)
        if row is None:
            row = EmailSettings(org_id=actor.org_id)
            self.session.add(row)
        rich = body_format == "html"
        cleaned = sanitize_body(body) if rich else body
        row.asset_email_subject = subject.strip() or None
        row.asset_email_body = cleaned.strip() or None
        row.asset_email_body_format = "html" if rich else "text"
        if cc is not None:
            row.asset_email_cc = _clean_cc(cc)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="email.asset_template",
            target_type="email_settings", target_id=row.domain or "",
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
    async def resolve_sender(
        session: AsyncSession, org_id: uuid.UUID, *, org_name: str
    ) -> OrgSender:
        """Who this org's mail goes out as. Always answers — there is no unsendable state.

        Two outcomes, and which one you get is the org's choice rather than a measure of
        how far through setup they are:

          own domain, verified   ->  From: Acme IT <it@acme.com>
          anything else          ->  From: Acme IT (via ASTRA) <astra@technomateai.com>

        The second is not a degraded mode. Getting DNS records added is a request to
        somebody else in most companies, and an org that has chosen not to do it still
        needs its asset emails delivered today.

        The single seam the OAuth methods will implement later. It is also the only one —
        this logic used to exist here AND inline in AssetService, which is how the two came
        to disagree about what the display name should be.
        """
        row = (await session.execute(
            select(EmailSettings).where(EmailSettings.org_id == org_id)
        )).scalar_one_or_none()

        if (
            row is not None
            and row.method is EmailSendMethod.DNS
            and row.status is EmailVerificationStatus.VERIFIED
            and row.from_address
        ):
            return OrgSender(
                from_name=row.from_name or org_name,
                from_address=row.from_address,
                reply_to=row.reply_to,
            )

        # "(via ASTRA)" is said out loud rather than hidden. The address is ours, and a
        # recipient who checks is going to see that anyway — better they read it as an
        # organization using a tool than as mail impersonating their IT department.
        return OrgSender(
            from_name=f"{(row.from_name if row else None) or org_name} (via ASTRA)",
            from_address=None,
            reply_to=row.reply_to if row else None,
            shared=True,
        )


def _status_from_payload(payload: dict) -> EmailVerificationStatus:
    # Resend domain status is one of: not_started, pending, verified, failed, temporary_failure.
    raw = (payload.get("status") or "").lower()
    if raw == "verified":
        return EmailVerificationStatus.VERIFIED
    if raw in ("failed",):
        return EmailVerificationStatus.FAILED
    return EmailVerificationStatus.PENDING
