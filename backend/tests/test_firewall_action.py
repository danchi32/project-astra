"""enable_firewall — the first Phase 2 fix action (2a+)."""
from datetime import UTC, datetime

from app.models import DevicePosture
from app.services.compliance import CHECK_FIX, ComplianceService
from app.services.remediation.actions import ACTIONS, RemediationTier


def test_it_is_an_approval_tier_action_run_by_the_elevated_service():
    action = ACTIONS["enable_firewall"]
    assert action.tier is RemediationTier.APPROVAL_REQUIRED
    assert action.execution_context == "system"
    assert action.params == ()                       # fixed command: nothing to point elsewhere


def test_the_ai_may_propose_it_but_a_person_approves():
    # Not withheld: a firewall that is off is a fault, and the approval gate stays in front of it.
    action = ACTIONS["enable_firewall"]
    assert not action.operator_only


def test_a_failing_firewall_check_offers_this_fix():
    assert CHECK_FIX["firewall"] == "enable_firewall"
    row = DevicePosture(device_id=None, org_id=None, firewall_domain=False, firewall_private=True,
                        firewall_public=False, collected_at=datetime.now(UTC))
    check = ComplianceService._firewall_check(row)
    assert check.status == "fail"
    assert check.fix_action_id == "enable_firewall"
    assert "domain" in check.detail and "public" in check.detail


def test_a_passing_firewall_check_offers_nothing():
    row = DevicePosture(device_id=None, org_id=None, firewall_domain=True, firewall_private=True,
                        firewall_public=True, collected_at=datetime.now(UTC))
    check = ComplianceService._firewall_check(row)
    assert check.status == "pass"
    assert check.fix_action_id is None


# ── security review fixes ──────────────────────────────────────────────────────────


def _posture(**kw):
    base = dict(device_id=None, org_id=None, collected_at=datetime.now(UTC))
    base.update(kw)
    return DevicePosture(**base)


def test_a_partly_reported_firewall_is_unknown_not_pass():
    check = ComplianceService._firewall_check(_posture(firewall_domain=True))
    assert check.status == "unknown"


def test_a_pc_protected_by_another_antivirus_passes_the_defender_check():
    check = ComplianceService._defender_check(_posture(defender_realtime=False, third_party_antivirus=True))
    assert check.status == "pass"
    # Without the other antivirus, real-time off is still a failure with the admin fix offered.
    off = ComplianceService._defender_check(_posture(defender_realtime=False, third_party_antivirus=False))
    assert off.status == "fail" and off.fix_action_id == "enable_defender_realtime"
