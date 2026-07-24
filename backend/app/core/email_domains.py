"""Personal / free email providers.

Their domains may back any number of independent organisations (many unrelated people
use gmail), so self-service signup does not enforce one-org-per-domain for them. Every
other (corporate) domain may register exactly one organisation."""

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
    }
)


def corporate_domain(email: str) -> str | None:
    """Return the domain to enforce single-organisation registration on, or None when the
    address is a personal/free provider (which may register independently any number of
    times). Matching is case-insensitive."""
    _, _, domain = (email or "").partition("@")
    domain = domain.strip().lower().rstrip(".")
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return None
    return domain
