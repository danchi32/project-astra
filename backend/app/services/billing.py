"""Stripe billing — licensed per-seat subscriptions.

Model: an org buys a fixed number of **licenses**. Billing is on the purchased
license count (predictable), and device enrollment is hard-capped at it (enforced
in DeviceService, a pure DB check — no Stripe needed to block enrollment).

Design:
* Inert until configured. With no ``stripe_secret_key``/``stripe_price_id`` the
  service reports ``enabled=False`` and every action is a safe no-op.
* Card data never touches this backend — the admin subscribes via Stripe Checkout
  and manages the card/plan via the Stripe Billing Portal.
* Webhooks are the source of truth for subscription state and the license count
  (kept equal to the Stripe subscription quantity).
* Discounts are operator-only: the super-admin sets a percent, realised as a Stripe
  coupon attached to the subscription and applied to future checkouts.
"""
from datetime import datetime, timezone

import stripe
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Device, Organization, SubscriptionStatus, User
from app.services.exceptions import ValidationError
from app.services.payments import SubscriptionEvent, available_providers, get_provider
from app.services.subscription import org_is_writable, read_only_reason

settings = get_settings()

_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "unpaid": SubscriptionStatus.PAST_DUE,
    "incomplete": SubscriptionStatus.PAST_DUE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
    "canceled": SubscriptionStatus.CANCELED,
    "paused": SubscriptionStatus.SUSPENDED,
}


def _to_dt(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def _sub_period_end(sub: dict) -> int | None:
    """`current_period_end` is on the subscription in older API versions and on the
    subscription item in newer ones (2025-03+). Check both."""
    if sub.get("current_period_end"):
        return sub["current_period_end"]
    items = (sub.get("items") or {}).get("data") or []
    if items and items[0].get("current_period_end"):
        return items[0]["current_period_end"]
    return None


def _sub_quantity(sub: dict) -> int | None:
    items = (sub.get("items") or {}).get("data") or []
    if items and items[0].get("quantity") is not None:
        return int(items[0]["quantity"])
    return None


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key

    # -- capability flags ------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(settings.stripe_secret_key)

    @property
    def can_checkout(self) -> bool:
        return bool(settings.stripe_secret_key and settings.stripe_price_id)

    @property
    def seat_type(self) -> str:
        return settings.billing_seat if settings.billing_seat in ("device", "user") else "device"

    # -- seats -----------------------------------------------------------------

    async def used_seats(self, org_id) -> int:
        """Seats in use = active devices (default) or active users for the org."""
        model = User if self.seat_type == "user" else Device
        n = (
            await self.session.execute(
                select(func.count())
                .select_from(model)
                .where(model.org_id == org_id, model.is_active.is_(True))
            )
        ).scalar_one()
        return int(n)

    # -- status ----------------------------------------------------------------

    async def status(self, org: Organization) -> dict:
        writable = org_is_writable(org)
        rails = available_providers()
        return {
            "billing_enabled": self.enabled or bool(rails),
            "providers": rails,
            "billing_provider": org.billing_provider,
            "plan": org.plan,
            "subscription_status": org.subscription_status.value,
            "writable": writable,
            "read_only_reason": None if writable else read_only_reason(org),
            "trial_ends_at": org.trial_ends_at,
            "current_period_end": org.current_period_end,
            "has_subscription": bool(org.provider_subscription_id or org.stripe_subscription_id),
            "seat_type": self.seat_type,
            "licenses": org.license_count,
            "seats_used": await self.used_seats(org.id),
            "discount_percent": org.discount_percent,
            "unit_price_configured": bool(settings.stripe_price_id),
        }

    # -- Payment rails (Razorpay = India, Paddle = international) ---------------

    async def create_rail_checkout(
        self, org: Organization, quantity: int, provider_name: str
    ) -> str:
        """Send the admin to the chosen rail to authorize payment."""
        provider = get_provider(provider_name)
        if provider is None or not provider.can_checkout:
            raise ValidationError(
                "That payment method isn't available. Contact ASTRA support."
            )
        used = await self.used_seats(org.id)
        quantity = max(1, quantity, used)  # never sell fewer licenses than are in use
        url = await provider.create_checkout(org=org, quantity=quantity)
        await self.session.commit()  # the provider stamped billing_provider/subscription id
        return url

    async def rail_portal_url(self, org: Organization) -> str | None:
        """Hosted management page, when the rail has one (Paddle does)."""
        provider = get_provider(org.billing_provider)
        if provider is None:
            return None
        portal = getattr(provider, "portal_url", None)
        return await portal(org) if portal else provider.manage_url(org)

    async def cancel_subscription(self, org: Organization) -> None:
        provider = get_provider(org.billing_provider)
        if provider is None:
            raise ValidationError("This organization has no subscription to cancel.")
        await provider.cancel(org=org)

    async def apply_event(self, event: SubscriptionEvent) -> dict:
        """Apply a rail's normalized webhook to the org. Webhooks are the source of
        truth for subscription_status (which drives the read-only gate) and licenses."""
        if event.ignored:
            return {"received": True, "applied": False}

        org = await self._org_for_event(event)
        if org is None:
            return {"received": True, "applied": False}

        if event.subscription_id:
            org.provider_subscription_id = event.subscription_id
        if event.customer_id:
            org.provider_customer_id = event.customer_id
        if event.status is not None:
            org.subscription_status = event.status
            org.plan = "per-seat" if event.status is SubscriptionStatus.ACTIVE else org.plan
        if event.quantity is not None:
            org.license_count = event.quantity
        if event.period_end is not None:
            org.current_period_end = event.period_end
        await self.session.commit()
        return {"received": True, "applied": True}

    async def _org_for_event(self, event: SubscriptionEvent) -> Organization | None:
        if event.org_id:
            org = await self.session.get(Organization, event.org_id)
            if org is not None:
                return org
        for column, value in (
            (Organization.provider_subscription_id, event.subscription_id),
            (Organization.provider_customer_id, event.customer_id),
        ):
            if value:
                org = (
                    await self.session.execute(select(Organization).where(column == value))
                ).scalars().first()
                if org is not None:
                    return org
        return None

    # -- Stripe customer / coupon ----------------------------------------------

    async def _ensure_customer(self, org: Organization) -> str:
        if org.stripe_customer_id:
            return org.stripe_customer_id
        customer = await run_in_threadpool(
            stripe.Customer.create, name=org.name, metadata={"org_id": str(org.id)}
        )
        org.stripe_customer_id = customer["id"]
        await self.session.commit()
        return customer["id"]

    async def _ensure_coupon(self, org: Organization) -> str | None:
        """A reusable Stripe coupon reflecting the org's operator discount."""
        if not org.discount_percent:
            return None
        if org.stripe_coupon_id:
            return org.stripe_coupon_id
        coupon = await run_in_threadpool(
            lambda: stripe.Coupon.create(
                percent_off=float(org.discount_percent),
                duration="forever",
                name=f"{org.discount_percent}% off",
            )
        )
        org.stripe_coupon_id = coupon["id"]
        await self.session.commit()
        return coupon["id"]

    # -- Checkout / Billing Portal ---------------------------------------------

    async def create_checkout_url(self, org: Organization, quantity: int) -> str:
        if not self.can_checkout:
            raise ValidationError("Billing is not configured on the server.")
        used = await self.used_seats(org.id)
        quantity = max(1, quantity, used)  # can't buy fewer licenses than already in use
        customer_id = await self._ensure_customer(org)
        coupon_id = await self._ensure_coupon(org)
        base = settings.public_app_url.rstrip("/")
        params = dict(
            mode="subscription",
            customer=customer_id,
            client_reference_id=str(org.id),
            line_items=[{"price": settings.stripe_price_id, "quantity": quantity}],
            subscription_data={"metadata": {"org_id": str(org.id)}},
            allow_promotion_codes=True,
            success_url=f"{base}/billing?checkout=success",
            cancel_url=f"{base}/billing?checkout=cancelled",
        )
        if coupon_id:
            params["discounts"] = [{"coupon": coupon_id}]
            params.pop("allow_promotion_codes")  # Stripe forbids both together
        session = await run_in_threadpool(lambda: stripe.checkout.Session.create(**params))
        return session["url"]

    async def create_portal_url(self, org: Organization) -> str:
        if not self.enabled:
            raise ValidationError("Billing is not configured on the server.")
        if not org.stripe_customer_id:
            raise ValidationError("This organization has no billing account yet. Subscribe first.")
        base = settings.public_app_url.rstrip("/")
        session = await run_in_threadpool(
            lambda: stripe.billing_portal.Session.create(
                customer=org.stripe_customer_id, return_url=f"{base}/billing"
            )
        )
        return session["url"]

    # -- License management (org admin) ----------------------------------------

    async def set_licenses(self, org: Organization, count: int) -> tuple[int, int, str]:
        """Change the number of purchased licenses on the org's existing subscription,
        via whichever rail it's on (Razorpay / Paddle / PayPal, or legacy Stripe). The
        provider prorates. Cannot drop below the number of seats already in use."""
        used = await self.used_seats(org.id)
        count = max(1, count)
        if count < used:
            raise ValidationError(
                f"You have {used} active {self.seat_type}(s) in use — remove some before "
                f"reducing to {count} licenses."
            )

        # Current rails: route through the org's provider (the same seam as cancel).
        provider = get_provider(org.billing_provider)
        if provider is not None and org.provider_subscription_id:
            await provider.set_quantity(org=org, quantity=count)
            org.license_count = count
            await self.session.commit()
            return count, used, f"Updated to {count} license(s)."

        # Legacy Stripe path, for any org still subscribed via Stripe.
        if self.enabled and org.stripe_subscription_id:
            sub = await run_in_threadpool(stripe.Subscription.retrieve, org.stripe_subscription_id)
            item = sub["items"]["data"][0]
            await run_in_threadpool(
                lambda: stripe.SubscriptionItem.modify(
                    item["id"], quantity=count, proration_behavior="create_prorations"
                )
            )
            org.license_count = count
            await self.session.commit()
            return count, used, f"Updated to {count} license(s)."

        raise ValidationError("No active subscription. Subscribe first to buy licenses.")

    # -- Discounts (super-admin only) ------------------------------------------

    async def apply_discount(self, org: Organization, percent: int) -> None:
        if not (1 <= percent <= 100):
            raise ValidationError("Discount must be between 1 and 100 percent.")
        org.discount_percent = percent
        org.stripe_coupon_id = None  # force a fresh coupon at the new rate
        if self.enabled:
            coupon_id = await self._ensure_coupon(org)
            if org.stripe_subscription_id and coupon_id:
                await run_in_threadpool(
                    lambda: stripe.Subscription.modify(
                        org.stripe_subscription_id, discounts=[{"coupon": coupon_id}]
                    )
                )
        await self.session.commit()

    async def remove_discount(self, org: Organization) -> None:
        org.discount_percent = None
        org.stripe_coupon_id = None
        if self.enabled and org.stripe_subscription_id:
            try:
                await run_in_threadpool(
                    lambda: stripe.Subscription.modify(org.stripe_subscription_id, discounts=[])
                )
            except Exception:
                pass  # best-effort; the DB state is authoritative for the portal
        await self.session.commit()

    # -- Webhooks (source of truth) --------------------------------------------

    async def handle_webhook(self, payload: bytes, signature: str | None) -> dict:
        if not settings.stripe_webhook_secret:
            raise ValidationError("Webhook secret not configured.")
        try:
            event = stripe.Webhook.construct_event(
                payload, signature or "", settings.stripe_webhook_secret
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise ValidationError(f"Invalid webhook signature: {exc}") from exc

        etype = event["type"]
        obj = event["data"]["object"]

        if etype == "checkout.session.completed":
            await self._on_checkout_completed(obj)
        elif etype in ("customer.subscription.updated", "customer.subscription.deleted",
                       "customer.subscription.created"):
            await self._on_subscription_event(obj)
        elif etype == "invoice.paid":
            await self._on_invoice(obj, SubscriptionStatus.ACTIVE)
        elif etype == "invoice.payment_failed":
            await self._on_invoice(obj, SubscriptionStatus.PAST_DUE)

        return {"received": True, "type": etype}

    async def _org_by(self, *, customer_id=None, subscription_id=None) -> Organization | None:
        stmt = select(Organization)
        if subscription_id:
            stmt = stmt.where(Organization.stripe_subscription_id == subscription_id)
        elif customer_id:
            stmt = stmt.where(Organization.stripe_customer_id == customer_id)
        else:
            return None
        return (await self.session.execute(stmt)).scalars().first()

    async def _on_checkout_completed(self, obj: dict) -> None:
        org = None
        if obj.get("client_reference_id"):
            org = await self.session.get(Organization, _as_uuid(obj["client_reference_id"]))
        if org is None:
            org = await self._org_by(customer_id=obj.get("customer"))
        if org is None:
            return
        org.stripe_customer_id = obj.get("customer") or org.stripe_customer_id
        sub_id = obj.get("subscription")
        if sub_id:
            org.stripe_subscription_id = sub_id
            sub = await run_in_threadpool(stripe.Subscription.retrieve, sub_id)
            org.subscription_status = _STATUS_MAP.get(sub["status"], SubscriptionStatus.ACTIVE)
            org.current_period_end = _to_dt(_sub_period_end(sub))
            qty = _sub_quantity(sub)
            if qty is not None:
                org.license_count = qty
        else:
            org.subscription_status = SubscriptionStatus.ACTIVE
        org.plan = "per-seat"
        await self.session.commit()

    async def _on_subscription_event(self, sub: dict) -> None:
        org = await self._org_by(subscription_id=sub.get("id"), customer_id=sub.get("customer"))
        if org is None:
            return
        org.stripe_subscription_id = sub.get("id") or org.stripe_subscription_id
        org.subscription_status = _STATUS_MAP.get(sub.get("status"), org.subscription_status)
        org.current_period_end = _to_dt(_sub_period_end(sub)) or org.current_period_end
        qty = _sub_quantity(sub)
        if qty is not None and sub.get("status") not in ("canceled", "incomplete_expired"):
            org.license_count = qty
        if sub.get("status") in ("canceled", "incomplete_expired"):
            org.plan = "trial"
            org.license_count = 0  # cancelled → uncapped again (back on trial rules)
        await self.session.commit()

    async def _on_invoice(self, invoice: dict, status: SubscriptionStatus) -> None:
        org = await self._org_by(
            subscription_id=invoice.get("subscription"), customer_id=invoice.get("customer")
        )
        if org is None:
            return
        org.subscription_status = status
        period_end = _invoice_period_end(invoice)
        if period_end:
            org.current_period_end = _to_dt(period_end)
        await self.session.commit()


def _as_uuid(value):
    import uuid
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _invoice_period_end(invoice: dict) -> int | None:
    lines = (invoice.get("lines") or {}).get("data") or []
    for line in lines:
        period = line.get("period") or {}
        if period.get("end"):
            return period["end"]
    return None
