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

# User-facing application processes the generic restart_application action may kill and
# relaunch. Least privilege: only these names are accepted, so the action can never be
# used to terminate a security agent or a system-critical process. Matched case-insensitively.
SAFE_APP_PROCESSES: frozenset[str] = frozenset(
    {
        "WINWORD", "EXCEL", "POWERPNT", "ONENOTE", "MSACCESS", "OUTLOOK",
        "slack", "Skype", "notepad", "notepad++", "firefox", "brave",
        "Acrobat", "AcroRd32", "Code", "onedrive", "WhatsApp", "Spotify",
        "Discord", "Zoom", "ms-teams", "chrome", "msedge",
    }
)


@dataclass(frozen=True)
class RemediationAction:
    id: str
    label: str
    tier: RemediationTier
    description: str
    # Names of parameters this action accepts (validated per-action in the service).
    params: tuple[str, ...] = field(default_factory=tuple)
    # Which agent process executes this action:
    #   "user"   → the desktop Tray, running in the logged-in user's session (default).
    #   "system" → the elevated Windows Service (LocalSystem), for machine-wide work
    #              that needs admin rights (e.g. cleaning C:\Windows\Temp).
    # The agent claims tasks per-context (GET /agent/tasks?context=), so a task is only
    # ever handed to the process that has the privilege to run it.
    execution_context: str = "user"


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
    RemediationAction("restart_application", "Restart an application", RemediationTier.AUTOMATIC,
                      "Closes and reopens a user application (kill + relaunch) to clear a hang or "
                      "a window that won't open. Limited to a safe allowlist of user apps.",
                      params=("process_name",)),
    RemediationAction("flush_dns", "Flush DNS cache", RemediationTier.AUTOMATIC,
                      "Clears the DNS resolver cache to fix name-resolution / website-loading issues."),
    RemediationAction("clear_temp", "Clear temporary files", RemediationTier.AUTOMATIC,
                      "Deletes the signed-in user's temp files to free disk space and clear "
                      "corrupt caches. Runs in the user session (does not touch system folders)."),
    RemediationAction("clear_system_temp", "Deep clean system temp", RemediationTier.AUTOMATIC,
                      "Clears machine-wide temp and caches — C:\\Windows\\Temp, the Prefetch "
                      "folder, the Windows Update download cache and Windows Error Reports — to "
                      "free disk space and speed up a slow device. Runs under the elevated "
                      "service; safe and self-rebuilding.",
                      execution_context="system"),
    RemediationAction("clear_browser_cache", "Clear browser cache", RemediationTier.AUTOMATIC,
                      "Clears the HTTP cache for Chrome, Edge and Firefox to fix slow or broken "
                      "page loads. Does NOT touch history, passwords, bookmarks or cookies."),
    RemediationAction("restart_chrome", "Restart Google Chrome", RemediationTier.AUTOMATIC,
                      "Closes and reopens Chrome to clear a hang or runaway memory use. Chrome "
                      "restores the previous tabs on relaunch."),
    RemediationAction("restart_edge", "Restart Microsoft Edge", RemediationTier.AUTOMATIC,
                      "Closes and reopens Microsoft Edge. Edge restores the previous tabs."),
    RemediationAction("restart_network_adapter", "Restart network adapter", RemediationTier.AUTOMATIC,
                      "Disables and re-enables the network adapter to recover a dropped connection."),
    RemediationAction("restart_service", "Restart a Windows service", RemediationTier.AUTOMATIC,
                      "Restarts an allowlisted Windows service (e.g. Print Spooler, Windows Search).",
                      params=("service_name",)),
    RemediationAction("create_outlook_rule", "Create an Outlook inbox rule", RemediationTier.AUTOMATIC,
                      "Creates a rule in the user's DESKTOP Outlook that moves incoming mail from a "
                      "given sender address into a folder (creating the folder if it doesn't exist). "
                      "Reversible — the user can delete the rule in Outlook.",
                      params=("from_address", "folder_name")),

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
