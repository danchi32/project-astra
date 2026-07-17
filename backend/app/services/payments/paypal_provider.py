"""PayPal rail — international customers (cross-border only).

Caveats worth remembering, since they shaped the design:
  * PayPal CANNOT process domestic Indian payments (cross-border only for Indian
    merchants since 2021) — Indian customers must use the Razorpay rail.
  * PayPal is NOT a merchant of record, so VAT/sales-tax compliance stays with us
    (unlike Paddle). It's the rail that's available *today*.
  * There is no hosted billing portal — customers manage subscriptions inside their
    own PayPal account, so we expose an in-app cancel instead.

Flow: create a Subscription against a per-seat Plan -> redirect the admin to the
`approve` link -> PayPal webhooks drive the org's subscription state.
Inert until paypal_client_id/secret are set.
"""
import json
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.models import Organization, SubscriptionStatus
from app.services.exceptions import ValidationError
from app.services.payments.base import SubscriptionEvent

settings = get_settings()

# PayPal subscription status -> our lifecycle status.
_STATUS_MAP = {
    "APPROVAL_PENDING": None,   # created, awaiting the customer's approval
    "APPROVED": None,           # approved but not yet billed
    "ACTIVE": SubscriptionStatus.ACTIVE,
    "SUSPENDED": SubscriptionStatus.SUSPENDED,
    "CANCELLED": SubscriptionStatus.CANCELED,
    "EXPIRED": SubscriptionStatus.CANCELED,
}

# Webhook event -> the status it implies when the resource doesn't carry one.
_EVENT_STATUS = {
    "BILLING.SUBSCRIPTION.ACTIVATED": SubscriptionStatus.ACTIVE,
    "BILLING.SUBSCRIPTION.RE-ACTIVATED": SubscriptionStatus.ACTIVE,
    "BILLING.SUBSCRIPTION.SUSPENDED": SubscriptionStatus.SUSPENDED,
    "BILLING.SUBSCRIPTION.CANCELLED": SubscriptionStatus.CANCELED,
    "BILLING.SUBSCRIPTION.EXPIRED": SubscriptionStatus.CANCELED,
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED": SubscriptionStatus.PAST_DUE,
}


def _to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


class PayPalProvider:
    name = "paypal"

    @property
    def _base(self) -> str:
        return (
            "https://api-m.sandbox.paypal.com"
            if settings.paypal_sandbox
            else "https://api-m.paypal.com"
        )

    @property
    def enabled(self) -> bool:
        return bool(settings.paypal_client_id and settings.paypal_client_secret)

    @property
    def can_checkout(self) -> bool:
        return bool(self.enabled and settings.paypal_plan_id)

    async def _token(self, client: httpx.AsyncClient) -> str:
        r = await client.post(
            f"{self._base}/v1/oauth2/token",
            auth=(settings.paypal_client_id or "", settings.paypal_client_secret or ""),
            data={"grant_type": "client_credentials"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            raise ValidationError(f"PayPal auth failed ({r.status_code}): {r.text[:200]}")
        return r.json()["access_token"]

    async def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await self._token(client)
            r = await client.request(
                method,
                f"{self._base}{path}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
        if r.status_code >= 400:
            raise ValidationError(f"PayPal error ({r.status_code}): {r.text[:300]}")
        return r.json() if r.content else {}

    # -- checkout --------------------------------------------------------------

    async def create_checkout(self, *, org: Organization, quantity: int) -> str:
        if not self.can_checkout:
            raise ValidationError("PayPal is not configured on the server.")
        base = (settings.public_app_url or "").rstrip("/")
        data = await self._request(
            "POST",
            "/v1/billing/subscriptions",
            {
                "plan_id": settings.paypal_plan_id,
                "quantity": str(max(1, quantity)),
                "custom_id": str(org.id),          # comes back on every webhook
                "application_context": {
                    "brand_name": "ASTRA",
                    "user_action": "SUBSCRIBE_NOW",
                    "return_url": f"{base}/billing?checkout=success",
                    "cancel_url": f"{base}/billing?checkout=cancelled",
                },
            },
        )
        org.billing_provider = self.name
        org.provider_subscription_id = data.get("id")
        for link in data.get("links") or []:
            if link.get("rel") == "approve":
                return link["href"]
        raise ValidationError("PayPal did not return an approval URL.")

    async def set_quantity(self, *, org: Organization, quantity: int) -> None:
        if not org.provider_subscription_id:
            raise ValidationError("This organization has no PayPal subscription yet.")
        # `revise` returns its own approval link when the change needs re-consent;
        # for a pure quantity change PayPal applies it directly.
        await self._request(
            "POST",
            f"/v1/billing/subscriptions/{org.provider_subscription_id}/revise",
            {"plan_id": settings.paypal_plan_id, "quantity": str(max(1, quantity))},
        )

    async def cancel(self, *, org: Organization) -> None:
        if not org.provider_subscription_id:
            raise ValidationError("This organization has no PayPal subscription yet.")
        await self._request(
            "POST",
            f"/v1/billing/subscriptions/{org.provider_subscription_id}/cancel",
            {"reason": "Cancelled from the ASTRA billing page"},
        )

    def manage_url(self, org: Organization) -> str | None:
        return None  # PayPal has no hosted portal — customers manage in their account.

    # -- webhooks --------------------------------------------------------------

    async def parse_webhook(self, *, payload: bytes, headers: dict[str, str]) -> SubscriptionEvent:
        """PayPal has no HMAC — authenticity is confirmed by asking PayPal itself."""
        if not settings.paypal_webhook_id:
            raise ValidationError("PayPal webhook id not configured.")
        try:
            event = json.loads(payload)
        except ValueError as exc:
            raise ValidationError("Malformed PayPal webhook payload.") from exc

        required = (
            "paypal-transmission-id",
            "paypal-transmission-time",
            "paypal-cert-url",
            "paypal-auth-algo",
            "paypal-transmission-sig",
        )
        if any(h not in headers for h in required):
            raise ValidationError("Missing PayPal signature headers.")

        verification = await self._request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            {
                "transmission_id": headers["paypal-transmission-id"],
                "transmission_time": headers["paypal-transmission-time"],
                "cert_url": headers["paypal-cert-url"],
                "auth_algo": headers["paypal-auth-algo"],
                "transmission_sig": headers["paypal-transmission-sig"],
                "webhook_id": settings.paypal_webhook_id,
                "webhook_event": event,
            },
        )
        if verification.get("verification_status") != "SUCCESS":
            raise ValidationError("Invalid PayPal webhook signature.")

        etype = event.get("event_type") or ""
        if not etype.startswith("BILLING.SUBSCRIPTION."):
            return SubscriptionEvent(ignored=True)

        resource = event.get("resource") or {}
        status = _STATUS_MAP.get(resource.get("status")) or _EVENT_STATUS.get(etype)
        quantity = resource.get("quantity")

        return SubscriptionEvent(
            org_id=_as_uuid(resource.get("custom_id")),
            subscription_id=resource.get("id"),
            customer_id=(resource.get("subscriber") or {}).get("payer_id"),
            status=status,
            quantity=int(quantity) if quantity else None,
            period_end=_to_dt(
                (resource.get("billing_info") or {}).get("next_billing_time")
            ),
            ignored=status is None,
        )


def _as_uuid(value):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
