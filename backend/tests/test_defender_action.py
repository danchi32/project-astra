"""enable_defender_realtime — admin-only fix action (2a+)."""
from app.services.remediation.actions import ACTIONS, RemediationTier


def test_it_is_admin_only_and_run_by_the_elevated_service():
    action = ACTIONS["enable_defender_realtime"]
    assert action.tier is RemediationTier.ADMIN_ONLY
    assert action.execution_context == "system"
    assert action.params == ()


def test_the_ai_cannot_request_it():
    # admin_only actions are refused to the assistant by its tool (app/services/ai/tools.py);
    # an admin starts it from the portal. It is not operator_only, which is a separate rule.
    from app.services.ai.tools import _ACTION_IDS
    assert "enable_defender_realtime" not in _ACTION_IDS
    assert not ACTIONS["enable_defender_realtime"].operator_only


def test_its_description_promises_no_tamper_protection_change():
    description = ACTIONS["enable_defender_realtime"].description
    assert "Tamper Protection" in description
    assert "Never changes" in description
