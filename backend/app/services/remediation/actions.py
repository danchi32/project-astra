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
                      "Disables and re-enables the network adapter to recover a dropped connection. "
                      "Briefly drops all connectivity, including the agent's own; it reports once "
                      "the link returns.",
                      execution_context="system"),
    RemediationAction("restart_service", "Restart a Windows service", RemediationTier.AUTOMATIC,
                      "Restarts an allowlisted Windows service (e.g. Print Spooler, Windows Search). "
                      "Stops and restarts dependent services with it.",
                      params=("service_name",), execution_context="system"),
    RemediationAction("create_outlook_rule", "Create an Outlook inbox rule", RemediationTier.AUTOMATIC,
                      "Creates a rule in the user's DESKTOP Outlook that moves incoming mail from a "
                      "given sender address into a folder (creating the folder if it doesn't exist). "
                      "Reversible — the user can delete the rule in Outlook.",
                      params=("from_address", "folder_name")),

    # ── Approval required: impactful but routine, needs IT sign-off ──────────
    RemediationAction("office_repair", "Repair Microsoft Office", RemediationTier.APPROVAL_REQUIRED,
                      "Runs Office's built-in quick repair for apps that crash or won't start "
                      "(Outlook, Word, Excel). FORCE-CLOSES every open Office app, losing unsaved "
                      "work — that is what the approval is for. Click-to-Run installs only "
                      "(Microsoft 365 / Office 2016+); older MSI installs are refused.",
                      execution_context="system"),
    RemediationAction("network_reset", "Reset network stack", RemediationTier.APPROVAL_REQUIRED,
                      "Resets Winsock and the TCP/IP stack for corruption that survives an adapter "
                      "restart. REQUIRES A REBOOT to take effect. Needs IT approval.",
                      execution_context="system"),
    RemediationAction("windows_update_install", "Install pending Windows updates", RemediationTier.APPROVAL_REQUIRED,
                      "Installs pending Windows updates via the elevated service. Pass kb_article_id "
                      "to install one specific update, or omit it to install all pending. Never "
                      "auto-reboots: reports when a restart is required. Needs IT approval.",
                      params=("kb_article_id",), execution_context="system"),

    # ── Admin only: high-risk, admin approval mandatory ─────────────────────
    #
    # `registry_fix` and `driver_update` used to be here. Both were catalogued but never
    # implemented by the agent, so the engine could propose one, an admin could approve it,
    # and the device would then refuse it — spending a human's approval on nothing. They are
    # gone rather than implemented, because neither can be made safe as a generic action:
    #   * registry_fix amounted to "write whatever the model decided" into the registry. An
    #     approver could not see what would be written, which makes the approval meaningless,
    #     and it is the opposite of the allowlisted-actions rule the rest of this file keeps.
    #   * driver_update has no safe vendor-neutral mechanism, and the failure mode is a
    #     machine that will not boot.
    # Specific, named registry fixes can be added as their own actions, where the approver can
    # see exactly what each one does.
    RemediationAction("reset_windows_update_components", "Reset Windows Update components",
                      RemediationTier.ADMIN_ONLY,
                      "Renames the SoftwareDistribution and catroot2 caches so Windows rebuilds "
                      "them — for updates that fail or download endlessly. Discards in-flight "
                      "downloads; the next update check is slow. Admin approval only.",
                      execution_context="system"),

    # ── Secure offboarding (elevated, admin-only): lock a local Windows account ──
    RemediationAction("disable_local_account", "Disable a local user account", RemediationTier.ADMIN_ONLY,
                      "Offboarding: disables a LOCAL Windows account and signs the user out now, so "
                      "they can't sign back in. Does NOT change the password or delete anything — "
                      "fully reversible with 'enable_local_account'. Local accounts only (domain/Entra "
                      "accounts are managed in AD/Intune). Elevated + admin approval only.",
                      params=("username",), execution_context="system"),
    RemediationAction("enable_local_account", "Re-enable a local user account", RemediationTier.ADMIN_ONLY,
                      "Reverses disable_local_account: re-activates the local account so the user can "
                      "sign in again with their existing password. Elevated + admin approval only.",
                      params=("username",), execution_context="system"),

    # ── Remove software the organization has restricted (elevated, admin-only) ──
    # Unlike every other action here, the permitted targets are NOT a constant in this
    # file: they are whatever the organization put on its own restricted-software list,
    # which is the entire point. The service checks the name against that list per request,
    # and against UNINSTALL_NEVER below, which no organization can override.
    RemediationAction("uninstall_application", "Uninstall restricted software",
                      RemediationTier.ADMIN_ONLY,
                      "Silently removes an application the organization has placed on its "
                      "restricted-software list. Machine-wide installations only, and only "
                      "where the vendor provides a silent uninstaller — an application that "
                      "would open a window is reported rather than removed, because nobody "
                      "would ever see that window. Elevated + admin approval only.",
                      params=("app_name",), execution_context="system"),

    # ── Self-service: things a person could do themselves, done for them ────────
    # Automatic because the user asked for their own machine and both are reversible.
    # They run in different processes for a reason that is easy to get wrong: the clock is
    # machine-wide and needs elevation, while a printer connection belongs to a user's
    # profile — added by the elevated service it would land in LocalSystem's profile and
    # the person who asked would never see it.
    RemediationAction("set_timezone", "Change the time zone", RemediationTier.AUTOMATIC,
                      "Sets the Windows time zone. Reversible, and the clock corrects itself "
                      "immediately — but every appointment in the person's calendar moves "
                      "with it, so the zone must be the one they actually meant.",
                      params=("timezone_id",), execution_context="system"),
    RemediationAction("add_network_printer", "Add a network printer", RemediationTier.AUTOMATIC,
                      "Connects the signed-in user to a shared printer by its network path "
                      "(\\\\server\\printer). Runs in that person's own session, because a "
                      "printer connection belongs to their profile and not to the machine.",
                      params=("printer_path",), execution_context="user"),

    # ── USB mass-storage control (elevated, admin-only) ─────────────────────────
    # A reversible pair, like the account lock. It disables the USB STORAGE driver only —
    # the one a pen drive or portable disk loads — and leaves keyboards, mice, webcams and
    # everything else untouched, because those load different drivers. A drive already
    # plugged in keeps working until it is unplugged; the block takes hold on the next
    # connection. No parameters: the action is the whole instruction.
    RemediationAction("block_usb_storage", "Block USB storage", RemediationTier.ADMIN_ONLY,
                      "Stops USB pen drives and portable disks from being used on this device, "
                      "to close the most common route data leaves on. Keyboards, mice, webcams "
                      "and other USB devices are unaffected. Reversible with 'unblock_usb_storage'. "
                      "Elevated + admin approval only.",
                      execution_context="system"),
    RemediationAction("unblock_usb_storage", "Allow USB storage", RemediationTier.ADMIN_ONLY,
                      "Reverses block_usb_storage: USB pen drives and portable disks work again "
                      "from the next time one is connected. Elevated + admin approval only.",
                      execution_context="system"),
)

# Windows time-zone identifiers ASTRA may set. An allowlist rather than a format check,
# because the value names a real place: a typo that still looked like an identifier would be
# accepted by tzutil, shift every meeting in the person's calendar, and give no clue why.
# Windows knows about 140; this is the set a business fleet actually asks for.
SAFE_TIMEZONES: frozenset[str] = frozenset({
    "UTC",
    # South Asia
    "India Standard Time", "Pakistan Standard Time", "Bangladesh Standard Time",
    "Sri Lanka Standard Time", "Nepal Standard Time",
    # Americas
    "Eastern Standard Time", "Central Standard Time", "Mountain Standard Time",
    "Pacific Standard Time", "Alaskan Standard Time", "Hawaiian Standard Time",
    "Atlantic Standard Time", "Canada Central Standard Time",
    "Central Standard Time (Mexico)", "E. South America Standard Time",
    "Argentina Standard Time",
    # Europe, Middle East, Africa
    "GMT Standard Time", "W. Europe Standard Time", "Central Europe Standard Time",
    "Romance Standard Time", "E. Europe Standard Time", "Russian Standard Time",
    "Turkey Standard Time", "Israel Standard Time", "Arabian Standard Time",
    "Arab Standard Time", "South Africa Standard Time",
    "W. Central Africa Standard Time", "E. Africa Standard Time",
    # Asia Pacific
    "SE Asia Standard Time", "Singapore Standard Time", "China Standard Time",
    "Tokyo Standard Time", "Korea Standard Time", "W. Australia Standard Time",
    "AUS Central Standard Time", "AUS Eastern Standard Time",
    "New Zealand Standard Time",
})

# Software ASTRA will never uninstall, whatever an organization lists as restricted.
# Removing endpoint protection across a fleet is precisely what someone who got into the
# portal would try, and disarming the agent would end the platform's own visibility. A
# restricted-software list is an IT policy; it is not a licence to strip a machine's
# defences. Matched as a case-insensitive substring, so vendor naming variants are covered.
UNINSTALL_NEVER: tuple[str, ...] = (
    "astra", "windows defender", "microsoft defender", "crowdstrike", "falcon",
    "sentinelone", "sophos", "mcafee", "symantec", "eset", "kaspersky",
    "trend micro", "carbon black", "cylance", "bitdefender", "webroot",
    "malwarebytes", "cortex xdr", "forticlient", "trellix",
)

ACTIONS: dict[str, RemediationAction] = {a.id: a for a in _ACTIONS}


def get_action(action_id: str) -> RemediationAction | None:
    return ACTIONS.get(action_id)
