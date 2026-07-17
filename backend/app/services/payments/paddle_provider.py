"""Paddle rail — international customers (Merchant of Record).

Paddle is the *seller of record*: it takes the payment, remits VAT/sales tax in
every jurisdiction, and pays out to your bank. That removes cross-border tax
compliance from ASTRA entirely — the reason to prefer it over PayPal when selling
software abroad from India.

Flow: create a Transaction against a per-seat Price -> redirect the admin to the
returned hosted checkout URL -> Paddle webhooks drive the org's subscription
state. Paddle also has a hosted customer portal, so "Manage billing" works.
Inert until paddle_api_key is set.
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

# Paddle subscription status -> our lifecycle status.
_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "paused": SubscriptionStatus.SUSPENDED,
    "canceled": SubscriptionStatus.CANCELED,
}


def _to_dt(value: str | None) -> datetime | None:
    """Paddle sends RFC3339, e.g. 2026-08-01T10:00:00.000Z."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


class PaddleProvider:
    name = "paddle"

    @property
    def _base(self) -> str:
        return "https://sandbox-api.paddle.com" if settings.paddle_sandbox else "https://api.paddle.com"

    @property
    def enabled(self) -> bool:
        return bool(settings.paddle_api_key)

    @property
    def can_checkout(self) -> bool:
        return bool(self.enabled and settings.paddle_price_id)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.paddle_api_key}"}

    async def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.request(
                method, f"{self._base}{path}", headers=self._headers(), json=body
            )
        if r.status_code >= 400:
            raise ValidationError(f"Paddle error ({r.status_code}): {r.text[:300]}")
        return (r.json() or {}).get("data", {})

    # -- checkout --------------------------------------------------------------

    async def create_checkout(self, *, org: Organization, quantity: int) -> str:
        if not self.can_checkout:
            raise ValidationError("Paddle is not configured on the server.")
        base = (settings.public_app_url or "").rstrip("/")
        data = await self._request(
            "POST",
            "/transactions",
            {
                "items": [{"price_id": settings.paddle_price_id, "quantity": max(1, quantity)}],
                "custom_data": {"org_id": str(org.id), "org_name": org.name},
                "checkout": {"url": f"{base}/billing?checkout=success"},
            },
        )
        org.billing_provider = self.name
        url = (data.get("checkout") or {}).get("url")
        if not url:
            raise ValidationError(
                "Paddle did not return a checkout URL — set a default payment link "
                "in Paddle > Checkout settings."
            )
        return url

    async def set_quantity(self, *, org: Organization, quantity: int) -> None:
        if not org.provider_subscription_id:
            raise ValidationError("This organization has no Paddle subscription yet.")
        await self._request(
            "PATCH",
            f"/subscriptions/{org.provider_subscription_id}",
            {
                "items": [{"price_id": settings.paddle_price_id, "quantity": max(1, quantity)}],
                "proration_billing_mode": "prorated_immediately",
            },
        )

    async def cancel(self, *, org: Organization) -> None:
        if not org.provider_subscription_id:
            raise ValidationError("This organization has no Paddle subscription yet.")
        await self._request(
            "POST",
            f"/subscriptions/{org.provider_subscription_id}/cancel",
            {"effective_from": "next_billing_period"},  # keep access until paid period ends
        )

    def manage_url(self, org: Organization) -> str | None:
        # Paddle's portal needs an API round-trip; see portal_url() below.
        return None

    async def portal_url(self, org: Organization) -> str | None:
        """Paddle's hosted customer portal (update card, invoices, cancel)."""
        if not (self.enabled and org.provider_customer_id):
            return None
        data = await self._request(
            "POST", f"/customers/{org.provider_customer_id}/portal-sessions", {}
        )
        return ((data.get("urls") or {}).get("general") or {}).get("overview")

    # -- webhooks --------------------------------------------------------------

    async def parse_webhook(self, *, payload: bytes, headers: dict[str, str]) -> SubscriptionEvent:
        secret = settings.paddle_webhook_secret
        if not secret:
            raise ValidationError("Paddle webhook secret not configured.")

        # Paddle-Signature: "ts=1671552777;h1=<hex hmac of `ts:body`>"
        raw = headers.get("paddle-signature") or ""
        parts = dict(p.split("=", 1) for p in raw.split(";") if "=" in p)
        ts, h1 = parts.get("ts"), parts.get("h1")
        if not ts or not h1:
            raise ValidationError("Malformed Paddle-Signature header.")
        expected = hmac.new(
            secret.encode(), f"{ts}:".encode() + payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, h1):
            raise ValidationError("Invalid Paddle webhook signature.")

        try:
            event = json.loads(payload)
        except ValueError as exc:
            raise ValidationError("Malformed Paddle webhook payload.") from exc

        etype = event.get("event_type") or ""
        data = event.get("data") or {}
        if not etype.startswith("subscription."):
            return SubscriptionEvent(ignored=True)

        status = _STATUS_MAP.get(data.get("status"))
        items = data.get("items") or []
        quantity = None
        if items and items[0].get("quantity") is not None:
            quantity = int(items[0]["quantity"])

        custom = data.get("custom_data") or {}
        return SubscriptionEvent(
            org_id=_as_uuid(custom.get("org_id")),
            subscription_id=data.get("id"),
            customer_id=data.get("customer_id"),
            status=status,
            quantity=quantity,
            period_end=_to_dt((data.get("current_billing_period") or {}).get("ends_at")),
            ignored=status is None,
        )


def _as_uuid(value):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
