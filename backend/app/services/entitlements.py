"""What each plan actually grants.

The single place a plan turns into features. Entitlements are DERIVED from the plan rather
than stored per organisation: a stored copy drifts from the plan the customer is paying for,
and then nobody can answer "this org is on Expert, why is compliance off". The override map
below exists for the cases that genuinely need it — a pilot, a grandfathered account — and is
deliberately small, visible and audited.

The feature list mirrors the public pricing page (website content.json). If the two disagree,
the site is the promise and this file is the bug.
"""
from __future__ import annotations

# ── Feature keys ───────────────────────────────────────────────────────────
# Named after what the customer is buying, not after the endpoint that happens to
# implement it — endpoints move, the promise doesn't.

INVENTORY = "inventory"                  # devices, assets, telemetry
PATCHING = "patching"                    # push Windows Updates
AI_DIAGNOSE = "ai_diagnose"              # the assistant explains what's wrong
REPORTING = "reporting"                  # dashboards + reports
NOTIFICATIONS = "notifications"          # alerts
AUDIT_VIEW = "audit_view"                # read the audit trail

AI_ACT = "ai_act"                        # the AI fixes things without a human clearing each one
APPROVAL_TIERS = "approval_tiers"
LOCKDOWN = "lockdown"                    # secure offboarding / disable an account
EMPLOYEE_CHAT = "employee_chat"

COMPLIANCE = "compliance"                # posture dashboard + scoring
BANNED_SOFTWARE = "banned_software"
FLEET_CORRELATION = "fleet_correlation"
FLEET_REMEDIATION = "fleet_remediation"  # one-click mass remediation
AUDIT_EXPORT = "audit_export"            # CSV export + extended retention
ADVANCED_RBAC = "advanced_rbac"          # incl. SSO

# ── Plans ──────────────────────────────────────────────────────────────────

ESSENTIAL = "essential"
PROFESSIONAL = "professional"
EXPERT = "expert"

#: Deliberately in Essential even though the pricing page lists them higher up.
#:
#: Audit VIEWING stays with everyone: this is a security product, and for many customers the
#: trail is their own compliance requirement — removing it would make the product a liability
#: rather than a cheaper tier. Expert's "full audit trail & export" is the CSV export and the
#: longer retention, which is what AUDIT_EXPORT covers.
#:
#: Notifications stay too: an Essential customer who is never told a device went offline
#: experiences a broken product, not a smaller one.
_ESSENTIAL: frozenset[str] = frozenset({
    INVENTORY, PATCHING, AI_DIAGNOSE, REPORTING, NOTIFICATIONS, AUDIT_VIEW,
})

_PROFESSIONAL: frozenset[str] = _ESSENTIAL | frozenset({
    AI_ACT, APPROVAL_TIERS, LOCKDOWN, EMPLOYEE_CHAT,
})

_EXPERT: frozenset[str] = _PROFESSIONAL | frozenset({
    COMPLIANCE, BANNED_SOFTWARE, FLEET_CORRELATION, FLEET_REMEDIATION,
    AUDIT_EXPORT, ADVANCED_RBAC,
})

PLANS: dict[str, frozenset[str]] = {
    ESSENTIAL: _ESSENTIAL,
    PROFESSIONAL: _PROFESSIONAL,
    EXPERT: _EXPERT,
}

PLAN_LABELS = {ESSENTIAL: "Essential", PROFESSIONAL: "Professional", EXPERT: "Expert"}

#: A trial shows the whole product. Someone evaluating ASTRA should see what they would be
#: buying; dropping them to Essential at signup means the features that justify the higher
#: tiers are the ones they never meet.
TRIAL_PLAN = EXPERT

#: Plans that predate feature tiers. Mapped to Expert, never to Essential: these orgs have
#: had every feature since they signed up, and silently taking paid functionality away from a
#: live customer is worse than any billing leak. The operator downgrades deliberately.
_LEGACY_PLANS = {"trial", "per-seat", "basic", "pro"}


def _plan_key(plan: str | None) -> str:
    """The stored plan value reduced to something `PLANS` can be looked up with.

    Stripped as well as lowercased. Falling back to Expert for an unknown plan is deliberate
    (below), but " essential " is not an unknown plan — it is Essential with a space, which
    is what a CSV import or a hand-edited row produces. Without the strip it fell through to
    the fallback and handed that customer the entire product.
    """
    return (plan or "").strip().lower()


def features_for(plan: str | None, overrides: dict | None = None) -> frozenset[str]:
    """Everything this org may use.

    An unrecognised plan resolves to Expert rather than to nothing. That is the deliberate
    choice: a typo in a plan name should not switch a paying customer's product off.
    """
    granted = set(PLANS.get(_plan_key(plan), _EXPERT))

    for key, on in (overrides or {}).items():
        if on:
            granted.add(key)
        else:
            granted.discard(key)
    return frozenset(granted)


def normalise_plan(plan: str | None) -> str:
    """The tier a stored plan value corresponds to, for display.

    Shares `_plan_key` with `features_for` on purpose: the label an admin is shown and the
    features they actually get must be derived from the same reading of the same string.
    """
    p = _plan_key(plan)
    if p in PLANS:
        return p
    return TRIAL_PLAN if p in _LEGACY_PLANS else EXPERT


class EntitlementError(Exception):
    """Raised when an org's plan doesn't include what was asked for.

    Its own type so the API can answer 402 rather than 403: the caller is allowed to do this,
    their plan just doesn't include it, and those need different words in the UI — one is
    "ask your admin", the other is "upgrade".
    """

    def __init__(self, feature: str, plan: str) -> None:
        self.feature = feature
        self.plan = plan
        super().__init__(
            f"{PLAN_LABELS.get(plan, plan.title())} doesn't include this feature."
        )
