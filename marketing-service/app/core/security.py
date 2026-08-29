"""Request signing for the public lead-intake endpoint.

The website is a static export on shared hosting, so the only thing that can call this
service is `contact.php`. That file already holds one secret (the sales@ mailbox password)
and gitignores it, so it is the right place to hold a second.

Why HMAC rather than a bearer token: the signature is derived from the body and a
timestamp, so it is not replayable and does not itself grant anything. A bearer token
leaked through a proxy log, an error report, or a misconfigured access log is a working
credential for as long as it takes anyone to notice. A leaked signature is worthless five
minutes later.
"""
import hashlib
import hmac
import logging
import time

logger = logging.getLogger("astra.mkt.security")


class SignatureError(Exception):
    """The request was not signed by someone holding the shared secret."""


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Produce the value the caller should send in X-Astra-Signature.

    The timestamp is inside the signed payload, not merely alongside it — otherwise an
    attacker could take a captured body and pair it with a fresh timestamp.
    """
    payload = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify(
    *, secret: str, timestamp: str | None, signature: str | None, body: bytes,
    max_skew_seconds: int,
) -> None:
    """Raise SignatureError unless the request is authentic and fresh.

    Order matters: the cheap checks run first so an unsigned flood costs almost nothing,
    and the comparison itself is constant-time so the endpoint does not leak the expected
    digest one byte at a time.
    """
    if not secret:
        # Not a client error. The operator has not configured the service, and falling
        # open here would put an unauthenticated write endpoint on the public internet.
        raise SignatureError("intake is not configured")
    if not timestamp or not signature:
        raise SignatureError("missing signature headers")

    try:
        sent_at = int(timestamp)
    except ValueError as exc:
        raise SignatureError("malformed timestamp") from exc

    skew = abs(int(time.time()) - sent_at)
    if skew > max_skew_seconds:
        raise SignatureError(f"timestamp outside the {max_skew_seconds}s window")

    if not hmac.compare_digest(sign(secret, timestamp, body), signature):
        raise SignatureError("signature mismatch")
