"""Subscription state helpers — the rules that decide whether an org can make
changes (write) based on its trial/billing status."""
from app.models import Organization, SubscriptionStatus
from app.models.base import as_utc, utcnow

TRIAL_DAYS = 14


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
