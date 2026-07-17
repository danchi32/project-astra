from app.services.payments.base import PaymentProvider, SubscriptionEvent
from app.services.payments.paddle_provider import PaddleProvider
from app.services.payments.razorpay_provider import RazorpayProvider

__all__ = ["PaymentProvider", "SubscriptionEvent", "PaddleProvider", "RazorpayProvider"]


def get_provider(name: str | None):
    """Resolve a rail by name. Razorpay = India, Paddle = international."""
    if name == "razorpay":
        return RazorpayProvider()
    if name == "paddle":
        return PaddleProvider()
    return None


def available_providers() -> list[str]:
    """Rails that are actually configured and able to sell right now."""
    return [p.name for p in (RazorpayProvider(), PaddleProvider()) if p.can_checkout]
