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
from app.services.exceptions import NotFoundError

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


@router.post("/checkout", response_model=CheckoutSession, summary="Subscribe (Stripe Checkout)")
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> CheckoutSession:
    org = await _load_org(user, session)
    url = await BillingService(session).create_checkout_url(org, body.quantity)
    return CheckoutSession(url=url)


@router.post("/portal", response_model=PortalSession, summary="Open the Stripe Billing Portal")
async def create_portal(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> PortalSession:
    org = await _load_org(user, session)
    return PortalSession(url=await BillingService(session).create_portal_url(org))


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
