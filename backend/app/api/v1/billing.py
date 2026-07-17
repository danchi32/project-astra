"""Billing endpoints — licensed per-seat subscriptions for the caller's own org.

The org admin subscribes via Stripe Checkout (choosing a license count) and manages
the card/plan via the Stripe Billing Portal; webhooks drive subscription state and
the license count. These routes are exempt from the read-only gate so an expired
org can still pay to reactivate.
"""
from fastapi import APIRouter, Depends, Request, status
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
from app.services.billing import BillingService
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
