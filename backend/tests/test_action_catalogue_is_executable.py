"""Every action the platform offers must actually be executable on a device.

This is the test that would have caught a real gap: `office_repair`, `registry_fix`,
`driver_update`, `network_reset`, `restart_service`, `restart_network_adapter` and
`reset_windows_update_components` were all in the catalogue and offered to the reasoning
engine, while no agent executor implemented any of them. The engine proposed them, admins
approved the gated ones, and the device then refused the work — so a person spent their
approval on something that could never run, and the user was told a fix was coming that
never arrived.

Nothing detected it because the two halves live in different languages and neither imports
the other. So the check reads the C# allowlists as text. That is crude, and deliberately so:
it fails loudly the moment the catalogue and the agent disagree, which is exactly when
someone is about to ship the gap again.
"""
import re
from pathlib import Path

from app.services.remediation.actions import ACTIONS, SAFE_SERVICES

AGENT = Path(__file__).resolve().parents[2] / "agent" / "src"
TRAY_EXECUTOR = AGENT / "AstraAgent.Tray" / "Remediation" / "RemediationExecutor.cs"
SYSTEM_EXECUTOR = AGENT / "AstraAgent.Service" / "Remediation" / "SystemRemediationExecutor.cs"
SERVICE_RESTARTER = AGENT / "AstraAgent.Service" / "Remediation" / "ServiceRestarter.cs"


def _allowlist(path: Path) -> set[str]:
    """The action ids inside an executor's `SupportedActions` initialiser."""
    body = re.search(r"SupportedActions\s*=.*?\{(.*?)\};", path.read_text(encoding="utf-8"), re.S)
    assert body, f"SupportedActions not found in {path.name}"
    return set(re.findall(r'"([a-z_]+)"', body.group(1)))


def test_every_offered_action_has_an_agent_implementation():
    implemented = _allowlist(TRAY_EXECUTOR) | _allowlist(SYSTEM_EXECUTOR)
    missing = sorted(a.id for a in ACTIONS.values() if a.id not in implemented)
    assert not missing, (
        "These actions are offered to the reasoning engine but no agent executor implements "
        f"them, so they fail on the device after being requested (and approved): {missing}. "
        "Either implement them in the agent or remove them from the catalogue."
    )


def test_actions_are_routed_to_the_executor_that_implements_them():
    """execution_context decides which process receives the task. Pointing an action at the
    wrong one fails at the device with 'not supported', which reads like a missing feature
    rather than a routing mistake."""
    tray, system = _allowlist(TRAY_EXECUTOR), _allowlist(SYSTEM_EXECUTOR)
    for action in ACTIONS.values():
        expected = system if action.execution_context == "system" else tray
        other = tray if action.execution_context == "system" else system
        if action.id in other and action.id not in expected:
            raise AssertionError(
                f"'{action.id}' is routed to the {action.execution_context} context but is only "
                f"implemented in the other one."
            )


def test_the_agent_permits_every_service_the_backend_allows():
    """Two allowlists guard restart_service — the backend's policy and the agent's own,
    independently (defense in depth). For that to be depth rather than contradiction, the
    agent's must be a superset: a service the backend permits but the agent refuses is a
    feature that silently does not work."""
    body = re.search(
        r"Allowed\s*=.*?\{(.*?)\};", SERVICE_RESTARTER.read_text(encoding="utf-8"), re.S
    )
    assert body, "Allowed dictionary not found in ServiceRestarter.cs"
    agent_services = {m.lower() for m in re.findall(r'\["([^"]+)"\]', body.group(1))}

    unsupported = sorted(s for s in SAFE_SERVICES if s.lower() not in agent_services)
    assert not unsupported, (
        f"The backend permits restarting {unsupported}, but ServiceRestarter refuses them."
    )


def test_removed_actions_stay_removed():
    """registry_fix meant 'write whatever the model decided' into the registry, with an
    approver who could not see what would be written; driver_update has no safe vendor-neutral
    mechanism and bricks machines when it is wrong. Both were catalogued and unimplemented.
    Re-adding either needs a deliberate design, not a one-line entry."""
    ids = set(ACTIONS)
    assert "registry_fix" not in ids
    assert "driver_update" not in ids
