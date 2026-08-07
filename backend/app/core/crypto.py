"""Encryption for credentials an organization entrusts to ASTRA.

A customer's Freshservice API key can read every ticket, contact and asset in their
helpdesk. Storing it as a column value means one database dump exposes every customer's
service desk at once — so it is encrypted at rest, and the key that decrypts it lives
outside the database.

Deliberately narrow: this is for third-party credentials we must be able to *use*, which
rules out hashing. It is not for passwords (bcrypt, one-way) and not for tokens we only
need to compare (hashed, see `hash_opaque_token`).

Inert without configuration, like every other integration here. With no key set, storing a
credential is refused rather than silently written in the clear — a plaintext secret nobody
knows is plaintext is worse than a feature that visibly will not turn on.
"""
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CryptoUnavailable(RuntimeError):
    """No encryption key is configured, so credentials cannot be stored or read."""


class DecryptionFailed(RuntimeError):
    """The stored value could not be decrypted with the configured key.

    Almost always means the key was rotated or replaced without re-encrypting. Raised
    rather than returning None so the caller reports "reconnect your helpdesk" instead of
    quietly behaving as though the org never configured one.
    """


def is_available() -> bool:
    return bool(get_settings().secrets_key)


def _fernet():
    from cryptography.fernet import Fernet  # imported lazily: unused without a key

    key = get_settings().secrets_key
    if not key:
        raise CryptoUnavailable(
            "ASTRA_SECRETS_KEY is not set — third-party credentials cannot be stored."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        # A malformed key is a deployment error, and it must not look like "no key".
        raise CryptoUnavailable(f"ASTRA_SECRETS_KEY is not a valid Fernet key: {exc}") from exc


def encrypt(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("Refusing to encrypt an empty value")
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionFailed(
            "Stored credential could not be decrypted — the encryption key has most "
            "likely changed since it was saved."
        ) from exc


def generate_key() -> str:
    """A new Fernet key, for setting ASTRA_SECRETS_KEY. Rotating it makes every existing
    stored credential undecryptable, so rotation means re-entering them."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def mask(secret: str | None) -> str:
    """What the portal shows instead of the credential. Enough to recognise which key is
    saved, never enough to use it."""
    if not secret:
        return ""
    tail = secret[-4:] if len(secret) > 4 else ""
    return f"{'•' * 8}{tail}"
