"""Razorpay rail — Indian customers (UPI / cards / netbanking / e-mandate, INR).

Razorpay is the only realistic way to charge Indian businesses: Stripe India is
invite-only, and PayPal cannot process domestic Indian payments at all (it has
been cross-border only for Indian merchants since 2021).

Flow: create a Subscription against a per-seat Plan -> redirect the admin to the
returned `short_url` -> Razorpay webhooks drive the org's subscription state.
Inert until razorpay_key_id/secret are set.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.models import Organization, SubscriptionStatus
from app.services.exceptions import ValidationError
from app.services.payments.base import SubscriptionEvent

settings = get_settings()

_API = "https://api.razorpay.com/v1"

# Razorpay subscription status -> our lifecycle status.
_STATUS_MAP = {
    "created": None,          # not authorized yet — leave the org as-is
    "authenticated": None,    # mandate approved, first charge pending
    "active": SubscriptionStatus.ACTIVE,
    "pending": SubscriptionStatus.PAST_DUE,    # a charge failed; retrying
    "halted": SubscriptionStatus.PAST_DUE,     # retries exhausted
    "cancelled": SubscriptionStatus.CANCELED,
    "completed": SubscriptionStatus.CANCELED,
    "expired": SubscriptionStatus.CANCELED,
}


def _to_dt(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


class RazorpayProvider:
    name = "razorpay"

    @property
    def enabled(self) -> bool:
        return bool(settings.razorpay_key_id and settings.razorpay_key_secret)

    @property
    def can_checkout(self) -> bool:
        return bool(self.enabled and settings.razorpay_plan_id)

    def _auth(self) -> tuple[str, str]:
        return (settings.razorpay_key_id or "", settings.razorpay_key_secret or "")

    async def _post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{_API}{path}", auth=self._auth(), json=body)
        if r.status_code >= 400:
            raise ValidationError(f"Razorpay error ({r.status_code}): {r.text[:300]}")
        return r.json()

    async def _patch(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(f"{_API}{path}", auth=self._auth(), json=body)
        if r.status_code >= 400:
            raise ValidationError(f"Razorpay error ({r.status_code}): {r.text[:300]}")
        return r.json()

    # -- checkout --------------------------------------------------------------

    async def create_checkout(self, *, org: Organization, quantity: int) -> str:
        if not self.can_checkout:
            raise ValidationError("Razorpay is not configured on the server.")
        sub = await self._post(
            "/subscriptions",
            {
                "plan_id": settings.razorpay_plan_id,
                "quantity": max(1, quantity),
                "total_count": 120,          # up to 120 billing cycles (10y monthly)
                "customer_notify": 1,
                "notes": {"org_id": str(org.id), "org_name": org.name},
            },
        )
        org.billing_provider = self.name
        org.provider_subscription_id = sub.get("id")
        url = sub.get("short_url")
        if not url:
            raise ValidationError("Razorpay did not return a checkout URL.")
        return url

    async def set_quantity(self, *, org: Organization, quantity: int) -> None:
        if not org.provider_subscription_id:
            raise ValidationError("This organization has no Razorpay subscription yet.")
        await self._patch(
            f"/subscriptions/{org.provider_subscription_id}",
            {"quantity": max(1, quantity), "schedule_change_at": "now"},
        )

    async def cancel(self, *, org: Organization) -> None:
        if not org.provider_subscription_id:
            raise ValidationError("This organization has no Razorpay subscription yet.")
        await self._post(
            f"/subscriptions/{org.provider_subscription_id}/cancel",
            {"cancel_at_cycle_end": 1},   # keep access until the paid period ends
        )

    def manage_url(self, org: Organization) -> str | None:
        return None  # Razorpay has no hosted portal; the portal exposes cancel in-app.

    # -- webhooks --------------------------------------------------------------

    async def parse_webhook(self, *, payload: bytes, headers: dict[str, str]) -> SubscriptionEvent:
        secret = settings.razorpay_webhook_secret
        if not secret:
            raise ValidationError("Razorpay webhook secret not configured.")
        signature = headers.get("x-razorpay-signature") or ""
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValidationError("Invalid Razorpay webhook signature.")

        try:
            event = json.loads(payload)
        except ValueError as exc:
            raise ValidationError("Malformed Razorpay webhook payload.") from exc

        entity = (
            event.get("payload", {}).get("subscription", {}).get("entity")
            or {}
        )
        if not entity:
            return SubscriptionEvent(ignored=True)

        notes = entity.get("notes") or {}
        org_id = notes.get("org_id")
        status = _STATUS_MAP.get(entity.get("status"))

        return SubscriptionEvent(
            org_id=_as_uuid(org_id),
            subscription_id=entity.get("id"),
            customer_id=entity.get("customer_id"),
            status=status,
            quantity=int(entity["quantity"]) if entity.get("quantity") is not None else None,
            period_end=_to_dt(entity.get("current_end")),
            ignored=status is None,
        )


def _as_uuid(value):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
