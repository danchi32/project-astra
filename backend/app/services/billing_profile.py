"""Billing identity and invoice history.

Deliberately separate from BillingService, which talks to the payment rails. This module
never calls a provider — it reads and writes what ASTRA knows about who is being billed and
what has been billed. Keeping them apart means a provider outage can't stop someone editing
their VAT number, and a change to invoice history can't accidentally touch a subscription.
"""
import uuid
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, InvoiceStatus, Organization, OrganizationBillingProfile
from app.schemas.billing_profile import (
    BillingProfileRead,
    BillingProfileUpdate,
    InvoiceRead,
)
from app.services.audit import AuditService

#: What an invoice cannot be produced without. Everything else on the profile is useful but
#: not blocking — a missing registration number never stopped an invoice being valid.
_REQUIRED_FOR_INVOICE = ("legal_name", "billing_email", "address_line1", "city", "country_code")

#: Columns a search may match. Deliberately not the tax id: searching by someone's VAT number
#: is not a thing anyone does, and matching on it invites a fishing query.
_SEARCHABLE = ("number", "transaction_id", "plan")

_SORTABLE = {
    "issued_on": Invoice.issued_on,
    "total": Invoice.total_cents,
    "status": Invoice.status,
    "renews_on": Invoice.renews_on,
    "number": Invoice.number,
}


class BillingProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Profile ────────────────────────────────────────────────────────────

    async def get_profile(self, *, org_id: uuid.UUID) -> BillingProfileRead:
        row = await self._row(org_id)
        read = BillingProfileRead.model_validate(row) if row else BillingProfileRead()
        read.complete = self._is_complete(row)
        return read

    async def update_profile(
        self, *, actor, org_id: uuid.UUID, data: BillingProfileUpdate
    ) -> BillingProfileRead:
        row = await self._row(org_id)
        if row is None:
            row = OrganizationBillingProfile(org_id=org_id)
            self.session.add(row)

        # exclude_unset so a form that only sends the fields it edited doesn't blank the rest.
        changed = data.model_dump(exclude_unset=True)
        for field, value in changed.items():
            setattr(row, field, value)

        await self.session.flush()
        await self.audit.record(
            org_id=org_id, actor_id=actor.id, action="billing.profile_update",
            target_type="billing_profile", target_id=str(row.id),
            # The values themselves are the customer's legal and tax identity — the log
            # records WHICH fields moved, not what they were set to.
            detail={"fields": sorted(changed.keys())},
        )
        await self.session.commit()
        await self.session.refresh(row)

        read = BillingProfileRead.model_validate(row)
        read.complete = self._is_complete(row)
        return read

    async def _row(self, org_id: uuid.UUID) -> OrganizationBillingProfile | None:
        return (await self.session.execute(
            select(OrganizationBillingProfile).where(
                OrganizationBillingProfile.org_id == org_id
            )
        )).scalar_one_or_none()

    @staticmethod
    def _is_complete(row: OrganizationBillingProfile | None) -> bool:
        if row is None:
            return False
        return all(getattr(row, f, None) for f in _REQUIRED_FOR_INVOICE)

    # ── Invoices ───────────────────────────────────────────────────────────

    async def list_invoices(
        self,
        *,
        org_id: uuid.UUID | None = None,
        q: str | None = None,
        status: list[InvoiceStatus] | None = None,
        issued_from: date | None = None,
        issued_to: date | None = None,
        sort: str = "issued_on",
        desc: bool = True,
        page: int = 1,
        page_size: int = 50,
        with_org_names: bool = False,
    ) -> tuple[list[InvoiceRead], int, int, int]:
        """One page of invoice history.

        `org_id` is None only for the operator's cross-org view; every customer-facing caller
        passes it, and the endpoint — not this method — is what proves the caller may.
        """
        from app.schemas.pagination import paginate

        stmt: Select = select(Invoice)
        if org_id is not None:
            stmt = stmt.where(Invoice.org_id == org_id)
        if status:
            stmt = stmt.where(Invoice.status.in_(status))
        if issued_from is not None:
            stmt = stmt.where(Invoice.issued_on >= issued_from)
        if issued_to is not None:
            stmt = stmt.where(Invoice.issued_on <= issued_to)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(or_(*[
                func.lower(getattr(Invoice, c)).like(like) for c in _SEARCHABLE
            ]))

        column = _SORTABLE.get(sort, Invoice.issued_on)
        stmt = stmt.order_by(column.desc() if desc else column.asc())

        rows, total, page, page_size = await paginate(
            self.session, stmt, page=page, page_size=page_size
        )
        items = [InvoiceRead.model_validate(r) for r in rows]

        if with_org_names and items:
            # Names for the page only — the operator's list shows an org column, and joining
            # the whole table to label 50 rows is the mistake this codebase keeps finding.
            names = dict((await self.session.execute(
                select(Organization.id, Organization.name).where(
                    Organization.id.in_({i.org_id for i in items})
                )
            )).all())
            for i in items:
                i.org_name = names.get(i.org_id)

        return items, total, page, page_size

    async def get_invoice(
        self, *, invoice_id: uuid.UUID, org_id: uuid.UUID | None = None
    ) -> Invoice | None:
        """`org_id` scopes the lookup. Passed by every customer-facing caller so a guessed
        invoice id from another organisation resolves to nothing rather than to a 403 that
        confirms the id exists."""
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        if org_id is not None:
            stmt = stmt.where(Invoice.org_id == org_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()
