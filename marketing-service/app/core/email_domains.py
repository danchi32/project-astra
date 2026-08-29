"""Personal / free email providers, for lead scoring.

Deliberately duplicated from `backend/app/core/email_domains.py` rather than imported.
The two services deploy independently and must not share a Python package; a marketing
scorer is also allowed to drift from the signup gate, because "gmail address" is a weak
negative signal here and a hard block there.
"""

FREE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com", "googlemail.com",
        "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.in", "ymail.com", "rocketmail.com",
        "outlook.com", "outlook.in", "hotmail.com", "hotmail.co.uk", "live.com", "msn.com",
        "icloud.com", "me.com", "mac.com",
        "aol.com", "gmx.com", "gmx.net", "mail.com",
        "protonmail.com", "proton.me", "pm.me", "tutanota.com", "tuta.io",
        "zoho.com", "zohomail.com", "yandex.com", "yandex.ru",
        "rediffmail.com", "hey.com", "fastmail.com", "hotmail.in",
        # Disposable / throwaway providers. Not "personal" so much as untraceable, but they
        # fail the same test: nobody's employer is mailcatch.com.
        "mailinator.com", "guerrillamail.com", "10minutemail.com", "yopmail.com",
        "temp-mail.org", "throwawaymail.com", "trashmail.com", "sharklasers.com",
        "getnada.com", "dispostable.com", "maildrop.cc", "mailcatch.com",
    }
)


def email_domain(email: str) -> str:
    """The lower-cased domain part of an address ("" when malformed)."""
    _, _, domain = (email or "").partition("@")
    return domain.strip().lower().rstrip(".")


def is_free_email_domain(email: str) -> bool:
    """True when the address belongs to a personal/free/disposable provider."""
    return email_domain(email) in FREE_EMAIL_DOMAINS
