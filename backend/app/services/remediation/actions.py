"""The remediation action registry — the authoritative catalogue of what the platform
is allowed to do to a device, and at what trust tier.

This registry is the security spine of self-healing. Only actions defined here can ever
be requested, and the tier controls whether execution is automatic or gated behind a
human approver. The Windows agent enforces a matching hardcoded allowlist independently
(defense in depth) — it never runs arbitrary commands.
"""
import enum
from dataclasses import dataclass, field


class RemediationTier(str, enum.Enum):
    AUTOMATIC = "automatic"            # safe, reversible — runs without human approval
    APPROVAL_REQUIRED = "approval_required"  # needs a technician or admin to approve
    ADMIN_ONLY = "admin_only"          # high-risk — only an admin may approve


# Services the platform is permitted to restart via the restart_service action. Anything
# outside this set is rejected, so the parameter can't be abused to touch a critical service.
SAFE_SERVICES: frozenset[str] = frozenset(
    {"Spooler", "WSearch", "Audiosrv", "Themes", "wuauserv"}
)


@dataclass(frozen=True)
class RemediationAction:
    id: str
    label: str
    tier: RemediationTier
    description: str
    # Names of parameters this action accepts (validated per-action in the service).
    params: tuple[str, ...] = field(default_factory=tuple)


_ACTIONS: tuple[RemediationAction, ...] = (
    # ── Automatic: safe, reversible endpoint hygiene ────────────────────────
    RemediationAction("restart_explorer", "Restart Windows Explorer", RemediationTier.AUTOMATIC,
                      "Restarts the Windows shell (explorer.exe) to fix a frozen taskbar or desktop."),
    RemediationAction("restart_outlook", "Restart Outlook", RemediationTier.AUTOMATIC,
                      "Closes and reopens Microsoft Outlook to clear a hang or sync issue."),
    RemediationAction("restart_teams", "Restart Microsoft Teams", RemediationTier.AUTOMATIC,
                      "Closes and reopens Microsoft Teams."),
    RemediationAction("restart_zoom", "Restart Zoom", RemediationTier.AUTOMATIC,
                      "Closes and reopens Zoom."),
    RemediationAction("flush_dns", "Flush DNS cache", RemediationTier.AUTOMATIC,
                      "Clears the DNS resolver cache to fix name-resolution / website-loading issues."),
    RemediationAction("clear_temp", "Clear temporary files", RemediationTier.AUTOMATIC,
                      "Deletes temp files to free disk space and clear corrupt caches."),
    RemediationAction("restart_network_adapter", "Restart network adapter", RemediationTier.AUTOMATIC,
                      "Disables and re-enables the network adapter to recover a dropped connection."),
    RemediationAction("restart_service", "Restart a Windows service", RemediationTier.AUTOMATIC,
                      "Restarts an allowlisted Windows service (e.g. Print Spooler, Windows Search).",
                      params=("service_name",)),

    # ── Approval required: impactful but routine, needs IT sign-off ──────────
    RemediationAction("office_repair", "Repair Microsoft Office", RemediationTier.APPROVAL_REQUIRED,
                      "Runs an Office quick/online repair. Disruptive; needs IT approval."),
    RemediationAction("driver_update", "Update a device driver", RemediationTier.APPROVAL_REQUIRED,
                      "Updates a hardware driver. Needs IT approval.", params=("device_class",)),
    RemediationAction("network_reset", "Reset network stack", RemediationTier.APPROVAL_REQUIRED,
                      "Resets Winsock/TCP-IP. Drops all connections; needs IT approval."),
    RemediationAction("windows_update_install", "Install pending Windows updates", RemediationTier.APPROVAL_REQUIRED,
                      "Installs pending Windows updates (may reboot). Needs IT approval."),

    # ── Admin only: high-risk, admin approval mandatory ─────────────────────
    RemediationAction("registry_fix", "Apply a registry fix", RemediationTier.ADMIN_ONLY,
                      "Applies an approved registry change. Admin approval only.", params=("fix_id",)),
    RemediationAction("reset_windows_update_components", "Reset Windows Update components",
                      RemediationTier.ADMIN_ONLY,
                      "Rebuilds the Windows Update component store. Admin approval only."),
)

ACTIONS: dict[str, RemediationAction] = {a.id: a for a in _ACTIONS}


def get_action(action_id: str) -> RemediationAction | None:
    return ACTIONS.get(action_id)
