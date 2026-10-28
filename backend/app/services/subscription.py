"""Subscription state helpers — the rules that decide whether an org can make
changes (write) based on its trial/billing status."""
import uuid
from time import monotonic

from sqlalchemy import event

from app.models import Organization, SubscriptionStatus
from app.models.base import as_utc, utcnow

TRIAL_DAYS = 14

# Device tokens (by SHA-256 hash, never the token itself) recently refused because their org is
# not writable: hash -> (refusal expires at, org id). An expired org's agents keep calling every
# minute, and each call used to be a device lookup plus an org lookup, which kept the database
# compute awake around the clock for orgs that can't use the product. A hit refuses before the
# request's session ever opens a connection.
#
# The TTL is long on purpose: a short one still put a lookup in every few minutes across a fleet
# of refused devices, so the database never got the idle gap it needs to scale to zero. The cost
# of a long TTL, an upgraded org being kept out, is removed by forgetting that org's entries the
# moment its subscription_status or trial_ends_at changes (the listeners below).
#
# ponytail: per-process memory. Ceiling: an org upgraded through one Cloud Run instance can still
# be refused by ANOTHER instance until the TTL lapses there. Prod runs one instance at this load.
# Upgrade path: a shared Redis set, invalidated on subscription change, once instances multiply.
REFUSED_TTL_SECONDS = 12 * 60 * 60
_REFUSED_MAX_ENTRIES = 50_000
_refused_tokens: dict[str, tuple[float, uuid.UUID]] = {}


def device_refused_recently(token_hash: str) -> bool:
    entry = _refused_tokens.get(token_hash)
    if entry is None:
        return False
    if entry[0] > monotonic():
        return True
    _refused_tokens.pop(token_hash, None)
    return False


def remember_device_refused(token_hash: str, org_id: uuid.UUID) -> None:
    now = monotonic()
    if len(_refused_tokens) >= _REFUSED_MAX_ENTRIES:
        for stale in [h for h, (until, _) in _refused_tokens.items() if until <= now]:
            del _refused_tokens[stale]
        if len(_refused_tokens) >= _REFUSED_MAX_ENTRIES:
            _refused_tokens.clear()  # bounded memory beats a perfect cache
    _refused_tokens[token_hash] = (now + REFUSED_TTL_SECONDS, org_id)


def forget_refused_org(org_id: uuid.UUID) -> None:
    """Let an org's devices straight back in — called whenever its subscription changes."""
    for token_hash in [h for h, (_, oid) in _refused_tokens.items() if oid == org_id]:
        _refused_tokens.pop(token_hash, None)


@event.listens_for(Organization.subscription_status, "set")
@event.listens_for(Organization.trial_ends_at, "set")
def _subscription_changed(target: Organization, _value, _old, _initiator) -> None:
    # Fires on assignment by any writer (billing webhooks, operator edits, trial extension),
    # including ones added later. Never on load. A rollback after it only costs one lookup.
    if target.id is not None:
        forget_refused_org(target.id)


def org_is_writable(org: Organization) -> bool:
    """Active orgs are writable; a trialing org is writable until its trial ends.
    Everything else (expired trial, past_due, suspended, canceled) is read-only —
    they can still view their data, but not make changes until they upgrade."""
    status = org.subscription_status
    if status is SubscriptionStatus.ACTIVE:
        return True
    if status is SubscriptionStatus.TRIALING:
        return org.trial_ends_at is None or as_utc(org.trial_ends_at) > utcnow()
    return False


def read_only_reason(org: Organization) -> str:
    if org.subscription_status is SubscriptionStatus.TRIALING:
        return "Your free trial has ended. Upgrade to keep making changes — your data is safe and still viewable."
    if org.subscription_status is SubscriptionStatus.PAST_DUE:
        return "Your last payment failed, so the account is read-only. Update your billing to continue."
    if org.subscription_status is SubscriptionStatus.SUSPENDED:
        return "This organization has been suspended. Contact ASTRA support."
    return "Your subscription has ended. Renew to continue making changes."
