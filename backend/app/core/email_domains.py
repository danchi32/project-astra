"""Personal / free email providers.

Two rules key off this list during self-service signup:

* **Work email required** (``ASTRA_REQUIRE_WORK_EMAIL``, on by default) — a personal
  provider cannot open an account at all. ASTRA is sold to organisations, and an org
  identified by a gmail address can't be verified, can't own a domain for the agent's
  enrollment story, and makes the one-org-per-domain rule below meaningless.
* **One organisation per corporate domain** — every other domain may register exactly
  once, so colleagues join the existing org instead of creating rival ones.

Operators are not bound by either: ``PlatformService.create_organization`` provisions
directly, so a genuine prospect on a personal address can still be onboarded by hand.
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


def is_free_email_domain(email: str) -> bool:
    """True when the address belongs to a personal/free/disposable provider."""
    return email_domain(email) in FREE_EMAIL_DOMAINS


def email_domain(email: str) -> str:
    """The lower-cased domain part of an address ("" when malformed)."""
    _, _, domain = (email or "").partition("@")
    return domain.strip().lower().rstrip(".")


def corporate_domain(email: str) -> str | None:
    """Return the domain to enforce single-organisation registration on, or None when the
    address is a personal/free provider. Matching is case-insensitive."""
    domain = email_domain(email)
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return None
    return domain
