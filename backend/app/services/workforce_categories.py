"""Built-in productivity classification for Workforce Insights ("Tracker").

Maps a foreground app or website to one of three buckets — productive / neutral /
unproductive — using the plan's default taxonomy (docs/WORKFORCE_INSIGHTS_PLAN.md §3.1). It
ships so the product works out of the box; the plan's per-org / per-team overrides and the
admin config UI are a later phase and would layer on top of this (resolution precedence:
team rule > org rule > this default > uncategorised=Neutral).

Deliberately a plain lookup, not a model: a surprising classification has to be traceable to
one rule, and "it matched this keyword / this domain" is the whole explanation.
"""
from __future__ import annotations

PRODUCTIVE = "productive"
NEUTRAL = "neutral"
UNPRODUCTIVE = "unproductive"
BUCKETS = (PRODUCTIVE, NEUTRAL, UNPRODUCTIVE)

# A category groups apps/domains that move together and gives the UI a human label. Order
# matters only for display; classification is by the maps below.
#: category_key -> (human label, default bucket)
CATEGORIES: dict[str, tuple[str, str]] = {
    "development": ("Development", PRODUCTIVE),
    "office": ("Office / docs", PRODUCTIVE),
    "design": ("Design", PRODUCTIVE),
    "work_comms": ("Work communication", PRODUCTIVE),
    "project": ("Project / ticketing", PRODUCTIVE),
    "crm_erp": ("CRM / ERP / finance", PRODUCTIVE),
    "cloud_admin": ("Cloud / admin consoles", PRODUCTIVE),
    "reference": ("Search / reference", NEUTRAL),
    "system": ("System / file / email", NEUTRAL),
    "news": ("News", NEUTRAL),
    "social": ("Social media", UNPRODUCTIVE),
    "streaming": ("Streaming / entertainment", UNPRODUCTIVE),
    "gaming": ("Gaming", UNPRODUCTIVE),
    "shopping": ("Shopping", UNPRODUCTIVE),
    "uncategorised": ("Uncategorised", NEUTRAL),
}

# Website domain (or any suffix of it) -> category. Checked by longest match so a specific
# host beats a bare domain.
_DOMAIN_CATEGORY: dict[str, str] = {
    "github.com": "development", "gitlab.com": "development", "stackoverflow.com": "development",
    "docs.google.com": "office", "sheets.google.com": "office", "office.com": "office",
    "figma.com": "design", "canva.com": "design",
    "teams.microsoft.com": "work_comms", "slack.com": "work_comms", "zoom.us": "work_comms",
    "meet.google.com": "work_comms", "outlook.office.com": "work_comms", "mail.google.com": "work_comms",
    "atlassian.net": "project", "jira.com": "project", "linear.app": "project",
    "asana.com": "project", "trello.com": "project", "notion.so": "project",
    "clickup.com": "project", "monday.com": "project",
    "salesforce.com": "crm_erp", "hubspot.com": "crm_erp", "zoho.com": "crm_erp",
    "sap.com": "crm_erp", "quickbooks.intuit.com": "crm_erp",
    "aws.amazon.com": "cloud_admin", "console.cloud.google.com": "cloud_admin",
    "portal.azure.com": "cloud_admin", "vercel.com": "cloud_admin",
    "google.com": "reference", "bing.com": "reference", "wikipedia.org": "reference",
    "news.google.com": "news", "bbc.com": "news", "ndtv.com": "news",
    "facebook.com": "social", "instagram.com": "social", "twitter.com": "social",
    "x.com": "social", "reddit.com": "social", "tiktok.com": "social", "snapchat.com": "social",
    "youtube.com": "streaming", "netflix.com": "streaming", "primevideo.com": "streaming",
    "spotify.com": "streaming", "hotstar.com": "streaming",
    "steampowered.com": "gaming", "epicgames.com": "gaming",
    "amazon.in": "shopping", "amazon.com": "shopping", "flipkart.com": "shopping", "myntra.com": "shopping",
}

# Process / app-name keyword (lowercased, substring) -> category.
_APP_CATEGORY: list[tuple[str, str]] = [
    ("code", "development"), ("devenv", "development"), ("visual studio", "development"),
    ("pycharm", "development"), ("intellij", "development"), ("goland", "development"),
    ("webstorm", "development"), ("rider", "development"), ("windowsterminal", "development"),
    ("powershell", "development"), ("cmd", "development"), ("git", "development"),
    ("winword", "office"), ("word", "office"), ("excel", "office"), ("powerpnt", "office"),
    ("powerpoint", "office"), ("onenote", "office"), ("acrobat", "office"), ("acrord32", "office"),
    ("figma", "design"), ("photoshop", "design"), ("illustrator", "design"), ("xd", "design"),
    ("teams", "work_comms"), ("ms-teams", "work_comms"), ("slack", "work_comms"),
    ("zoom", "work_comms"), ("outlook", "work_comms"),
    ("notion", "project"), ("jira", "project"),
    ("explorer", "system"), ("settings", "system"), ("systemsettings", "system"),
    ("steam", "gaming"), ("epicgameslauncher", "gaming"),
    ("spotify", "streaming"), ("vlc", "streaming"),
]


# Domains whose PATH must never be stored, even in path mode — banking/health/gov, where a
# path alone ("/accounts/transfer", "/patient/records") is sensitive (plan §6). A built-in
# default; the admin's own exclusion list layers on top in a later phase. Matched generously
# on purpose: over-excluding costs a little productivity detail, under-excluding stores
# something that should never have been kept.
_SENSITIVE_SUFFIXES = (".gov", ".gov.in", ".gov.uk", ".mil", ".nic.in")
_SENSITIVE_DOMAINS = frozenset({
    "paypal.com", "razorpay.com", "stripe.com", "hdfcbank.com", "icicibank.com",
    "sbi.co.in", "axisbank.com", "kotak.com", "chase.com", "bankofamerica.com",
    "wellsfargo.com", "nhs.uk", "who.int", "practo.com", "1mg.com", "apollopharmacy.in",
})
_SENSITIVE_KEYWORDS = ("bank", "insurance", "medical", "health", "hospital", "clinic", "pharma")

#: What a sensitive site is recorded as — never its domain or path.
PRIVATE_PLACEHOLDER = "(private site)"


def is_sensitive(domain: str | None) -> bool:
    if not domain:
        return False
    d = domain.strip().lower()
    if d in _SENSITIVE_DOMAINS or any(d.endswith("." + s) for s in _SENSITIVE_DOMAINS):
        return True
    if any(d.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES):
        return True
    return any(keyword in d for keyword in _SENSITIVE_KEYWORDS)


def _normalise_domain(domain: str) -> str:
    d = domain.strip().lower()
    if d.startswith("www."):
        d = d[4:]
    return d


def category_for(app: str | None, domain: str | None) -> str:
    """The category key for a foreground sample. Website wins over app — a browser's process
    name is just "chrome", but the domain says what the person is actually doing."""
    if domain:
        d = _normalise_domain(domain)
        # Longest suffix match: "docs.google.com" beats "google.com".
        best: str | None = None
        for known, cat in _DOMAIN_CATEGORY.items():
            if d == known or d.endswith("." + known):
                if best is None or len(known) > len(best):
                    best, best_cat = known, cat
        if best is not None:
            return best_cat
    if app:
        a = app.strip().lower()
        for keyword, cat in _APP_CATEGORY:
            if keyword in a:
                return cat
    return "uncategorised"


def classify(app: str | None, domain: str | None) -> tuple[str, str]:
    """(bucket, category_label) for a foreground sample."""
    cat = category_for(app, domain)
    label, bucket = CATEGORIES[cat]
    return bucket, label
