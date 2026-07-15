"""Billing endpoints — per-seat Stripe subscriptions for the caller's own org.

The org admin subscribes via Stripe Checkout and manages the card/plan via the
Stripe Billing Portal; webhooks drive the subscription state. These routes are
exempt from the read-only gate so an expired org can still pay to reactivate.
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Organization, User, UserRole
from app.schemas.billing import (
    BillingStatus,
    CheckoutSession,
    PortalSession,
    SeatSyncResult,
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


@router.post("/checkout", response_model=CheckoutSession, summary="Start a subscription (Stripe Checkout)")
async def create_checkout(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> CheckoutSession:
    org = await _load_org(user, session)
    return CheckoutSession(url=await BillingService(session).create_checkout_url(org))


@router.post("/portal", response_model=PortalSession, summary="Open the Stripe Billing Portal")
async def create_portal(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> PortalSession:
    org = await _load_org(user, session)
    return PortalSession(url=await BillingService(session).create_portal_url(org))


@router.post("/sync-seats", response_model=SeatSyncResult, summary="Reconcile seat quantity with Stripe")
async def sync_seats(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> SeatSyncResult:
    org = await _load_org(user, session)
    synced, count, detail = await BillingService(session).sync_seats(org)
    return SeatSyncResult(synced=synced, seat_count=count, detail=detail)


@router.post("/webhook", status_code=status.HTTP_200_OK, summary="Stripe webhook (no auth; signed)")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    return await BillingService(session).handle_webhook(payload, signature)
