from app.services.payments.base import PaymentProvider, SubscriptionEvent
from app.services.payments.paddle_provider import PaddleProvider
from app.services.payments.paypal_provider import PayPalProvider
from app.services.payments.razorpay_provider import RazorpayProvider

__all__ = [
    "PaymentProvider",
    "SubscriptionEvent",
    "PaddleProvider",
    "PayPalProvider",
    "RazorpayProvider",
]

# Razorpay = India (UPI/cards/netbanking). Paddle + PayPal = international;
# Paddle is a merchant of record (handles global VAT), PayPal is not.
_RAILS = {
    "razorpay": RazorpayProvider,
    "paddle": PaddleProvider,
    "paypal": PayPalProvider,
}


def get_provider(name: str | None):
    """Resolve a rail by name."""
    cls = _RAILS.get(name or "")
    return cls() if cls else None


def available_providers() -> list[str]:
    """Rails that are actually configured and able to sell right now."""
    return [name for name, cls in _RAILS.items() if cls().can_checkout]
