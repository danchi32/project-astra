"""enable_defender_realtime — admin-only fix action (2a+)."""
from app.services.remediation.actions import ACTIONS, RemediationTier


def test_it_is_admin_only_and_run_by_the_elevated_service():
    action = ACTIONS["enable_defender_realtime"]
    assert action.tier is RemediationTier.ADMIN_ONLY
    assert action.execution_context == "system"
    assert action.params == ()


def test_it_is_not_withheld_from_the_ai_but_a_person_still_has_to_approve():
    # admin_only: the AI may propose it, and only an admin can approve it. Not operator_only.
    assert not ACTIONS["enable_defender_realtime"].operator_only


def test_its_description_promises_no_tamper_protection_change():
    description = ACTIONS["enable_defender_realtime"].description
    assert "Tamper Protection" in description
    assert "Never changes" in description
