"""Billing endpoints — licensed per-seat subscriptions for the caller's own org.

The org admin subscribes via Stripe Checkout (choosing a license count) and manages
the card/plan via the Stripe Billing Portal; webhooks drive subscription state and
the license count. These routes are exempt from the read-only gate so an expired
org can still pay to reactivate.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Organization, User, UserRole
from app.schemas.billing import (
    BillingStatus,
    CheckoutRequest,
    CheckoutSession,
    LicenseResult,
    LicenseUpdate,
    PortalSession,
)
from app.models.invoice import InvoiceStatus
from app.schemas.billing_profile import (
    BillingProfileRead,
    BillingProfileUpdate,
    InvoiceRead,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build
from app.services.billing import BillingService
from app.services.billing_profile import BillingProfileService
from app.services.exceptions import NotFoundError
from app.services.exceptions import NotFoundError, ValidationError
from app.services.payments import PaddleProvider, PayPalProvider, RazorpayProvider

router = APIRouter(prefix="/billing", tags=["billing"])


async def _load_org(user: User, session: AsyncSession) -> Organization:
    org = await session.get(Organization, user.org_id)
    if org is None:
        raise NotFoundError("Organization not found")
    return org


@router.get("/status", response_model=BillingStatus, summary="Billing status for my org")
async def billing_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BillingStatus:
    org = await _load_org(user, session)
    return BillingStatus(**await BillingService(session).status(org))


@router.post("/checkout", response_model=CheckoutSession, summary="Subscribe (choose a payment rail)")
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> CheckoutSession:
    """`provider` picks the rail: 'razorpay' (India — UPI/cards/netbanking) or
    'paddle' (international — Merchant of Record). Falls back to Stripe when no
    rail is named, for backward compatibility."""
    org = await _load_org(user, session)
    service = BillingService(session)
    if body.provider:
        url = await service.create_rail_checkout(org, body.quantity, body.provider)
    else:
        url = await service.create_checkout_url(org, body.quantity)
    return CheckoutSession(url=url)


@router.post("/portal", response_model=PortalSession, summary="Open the hosted billing portal")
async def create_portal(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> PortalSession:
    org = await _load_org(user, session)
    service = BillingService(session)
    if org.billing_provider:  # Paddle has a hosted portal; Razorpay doesn't.
        url = await service.rail_portal_url(org)
        if not url:
            raise ValidationError(
                "Your payment provider has no self-serve portal. Use 'Cancel subscription', "
                "or contact ASTRA support to change your payment details."
            )
        return PortalSession(url=url)
    return PortalSession(url=await service.create_portal_url(org))


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel the subscription")
async def cancel_subscription(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Cancels at the end of the paid period — access continues until then."""
    org = await _load_org(user, session)
    await BillingService(session).cancel_subscription(org)


@router.post("/licenses", response_model=LicenseResult, summary="Add or remove licenses")
async def set_licenses(
    body: LicenseUpdate,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> LicenseResult:
    org = await _load_org(user, session)
    licenses, used, detail = await BillingService(session).set_licenses(org, body.count)
    return LicenseResult(licenses=licenses, seats_used=used, detail=detail)


@router.post("/webhook", status_code=status.HTTP_200_OK, summary="Stripe webhook (no auth; signed)")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    return await BillingService(session).handle_webhook(payload, signature)


# Rail webhooks — no auth: each is authenticated by its own HMAC signature, which
# is the boundary that stops anyone from marking an org as paid.
@router.post(
    "/webhook/paddle",
    status_code=status.HTTP_200_OK,
    summary="Paddle webhook (no auth; HMAC-signed)",
)
async def paddle_webhook(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
    payload = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    event = await PaddleProvider().parse_webhook(payload=payload, headers=headers)
    return await BillingService(session).apply_event(event)


@router.post(
    "/webhook/paypal",
    status_code=status.HTTP_200_OK,
    summary="PayPal webhook (no auth; verified with PayPal)",
)
async def paypal_webhook(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
    payload = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    event = await PayPalProvider().parse_webhook(payload=payload, headers=headers)
    return await BillingService(session).apply_event(event)


@router.post(
    "/webhook/razorpay",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook (no auth; HMAC-signed)",
)
async def razorpay_webhook(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
    payload = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    event = await RazorpayProvider().parse_webhook(payload=payload, headers=headers)
    return await BillingService(session).apply_event(event)


# ── Billing identity + invoice history (org-scoped) ─────────────────────────
#
# Added to the existing billing router rather than a new one, so the exemptions and role
# rules already declared here keep applying — an org whose subscription lapsed still needs
# to read its own invoices and correct its VAT number.


@router.get(
    "/profile",
    response_model=BillingProfileRead,
    summary="This organization's billing and tax details",
)
async def get_billing_profile(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BillingProfileRead:
    return await BillingProfileService(session).get_profile(org_id=actor.org_id)


@router.patch(
    "/profile",
    response_model=BillingProfileRead,
    summary="Update this organization's billing and tax details (admin)",
)
async def update_billing_profile(
    body: BillingProfileUpdate,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> BillingProfileRead:
    """Admin-only, and scoped to the caller's own org by construction — the org id comes
    from the token, never from the request, so there is no id to tamper with."""
    return await BillingProfileService(session).update_profile(
        actor=actor, org_id=actor.org_id, data=body
    )


@router.get(
    "/invoices",
    response_model=Page[InvoiceRead],
    summary="This organization's billing history",
)
async def list_invoices(
    q: str | None = None,
    status_in: list[InvoiceStatus] | None = Query(default=None, alias="status"),
    issued_from: date | None = None,
    issued_to: date | None = None,
    sort: str = "issued_on",
    desc: bool = True,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Page[InvoiceRead]:
    items, total, page, page_size = await BillingProfileService(session).list_invoices(
        org_id=actor.org_id, q=q, status=status_in,
        issued_from=issued_from, issued_to=issued_to,
        sort=sort, desc=desc, page=page, page_size=page_size,
    )
    return build(items, total, page, page_size)


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="One invoice from this organization's history",
)
async def get_invoice(
    invoice_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> InvoiceRead:
    # Scoped by org in the query: an id belonging to another organization resolves to
    # nothing, rather than to a 403 that would confirm the id is real.
    invoice = await BillingProfileService(session).get_invoice(
        invoice_id=invoice_id, org_id=actor.org_id
    )
    if invoice is None:
        raise NotFoundError("Invoice not found")
    return InvoiceRead.model_validate(invoice)
