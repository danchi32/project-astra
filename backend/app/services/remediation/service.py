import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Device,
    Message,
    MessageRole,
    NotificationCategory,
    NotificationSeverity,
    RemediationSource,
    RemediationStatus,
    RemediationTask,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.repositories.devices import DeviceRepository

settings = get_settings()
from app.repositories.remediation import RemediationRepository
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.notifications import NotificationService
from app.services.settings import SettingsService
from app.services.entitlements import AI_ACT, LOCKDOWN
from app.services.remediation.actions import (
    ACTIONS,
    SAFE_APP_PROCESSES,
    SAFE_SERVICES,
    SAFE_TIMEZONES,
    RemediationTier,
    get_action,
)


logger = logging.getLogger(__name__)


class RemediationError(ServiceError):
    pass


class AlreadyQueuedError(RemediationError):
    """The same action is already queued or running on this device.

    Its own type, rather than a plain RemediationError, because this is not a failure —
    the work the caller wants is already happening. Callers report it as such: a bulk push
    counts these separately from real failures, and the portal tells the operator the fix
    is already running instead of showing an error.
    """

    def __init__(self, message: str, existing: "RemediationTask") -> None:
        super().__init__(message)
        self.existing = existing


import re  # noqa: E402

# How long a queued-or-running task blocks an identical one. Matches the agent's own
# per-action execution cap, so a device whose agent died mid-action is not locked out of
# retrying that exact action forever — the one case where retrying matters most.
_IN_FLIGHT_WINDOW = timedelta(minutes=60)

# How each blocking state is described to the operator. "Waiting for approval" and "running
# on the device right now" call for completely different responses, so the message says which.
_STATE_WORDS = {
    RemediationStatus.PENDING_APPROVAL: "waiting for approval",
    RemediationStatus.APPROVED: "queued",
    RemediationStatus.DISPATCHED: "already running",
}

# Secure offboarding — the pair that disables and re-enables a local Windows account.
_LOCKDOWN_ACTIONS = frozenset({"disable_local_account", "enable_local_account"})

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Mailbox folder name: letters/digits/space and a few safe punctuation marks only —
# no path separators or control chars, so the parameter can't be abused.
_FOLDER_RE = re.compile(r"^[\w \-&().]{1,64}$", re.UNICODE)


def _validate_email(value: Any) -> str:
    email = (value or "").strip()
    if not _EMAIL_RE.match(email):
        raise RemediationError(f"'{value}' is not a valid sender email address.")
    return email


def _validate_folder_name(value: Any) -> str:
    name = (value or "").strip()
    if not _FOLDER_RE.match(name):
        raise RemediationError(
            "Folder name may only contain letters, numbers, spaces and - & ( ) . "
            "and be 1-64 characters."
        )
    return name


_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9 ._-]{0,62}[A-Za-z0-9.])?$")


#: A Windows share path and nothing else: two backslashes, a host, one backslash, a share.
#: The characters Windows itself forbids in a share name are excluded, which also leaves no
#: room for a path that walks somewhere else. The value is passed as a single argv element,
#: never through a shell, so this is about naming a real printer rather than about quoting.
_UNC_PRINTER = re.compile(r"\A\\\\[A-Za-z0-9][A-Za-z0-9._-]{0,62}\\[^\\/:*?\"<>|]{1,80}\Z")


def _validate_printer_path(value: Any) -> str:
    path = value.strip() if isinstance(value, str) else ""
    if not path:
        raise RemediationError("A printer path is required, e.g. \\\\printserver\\reception.")
    if not _UNC_PRINTER.match(path):
        raise RemediationError(
            f"'{path}' is not a printer network path. It should look like "
            "\\\\printserver\\reception."
        )
    return path


def _validate_timezone(value: Any) -> str:
    name = value.strip() if isinstance(value, str) else ""
    if not name:
        raise RemediationError("A time zone is required.")
    if name not in SAFE_TIMEZONES:
        raise RemediationError(
            f"'{name}' is not a Windows time zone ASTRA can set. Use an identifier such as "
            "'India Standard Time' or 'Eastern Standard Time'."
        )
    return name


def _validate_username(value: Any) -> str:
    """A local Windows account name. Deliberately strict — no characters that Windows forbids
    in account names or that could be abused when the agent hands the name to `net user`
    (the agent also passes it as a single argv element, never through a shell)."""
    name = str(value or "").strip()
    # Devices report the signed-in user as "DOMAIN\\user" (DOMAIN is the machine name for a
    # local account) — keep only the account part so a prefilled name validates.
    if "\\" in name:
        name = name.rsplit("\\", 1)[-1].strip()
    if not _USERNAME_RE.match(name) or any(c in name for c in '"/\\[]:;|=,+*?<>@'):
        raise RemediationError(
            f"'{value}' is not a valid local Windows account name."
        )
    return name


def _validate_session_id(value: Any) -> str:
    """Windows' own session id, carried as a string like every other parameter.

    Range-checked rather than merely parsed. Session 0 is the services session — it has no
    desktop and nobody is signed into it, so every action addressed to it is a mistake, and
    on a machine where the caller meant "the console" it is a mistake that does nothing
    while reporting success. The upper bound is not a Windows limit; it is a sanity bound
    that keeps an obviously-wrong number from reaching the agent at all.
    """
    raw = str(value).strip() if value is not None else ""
    if not raw.isdigit():
        raise RemediationError("A numeric Windows session id is required.")
    session_id = int(raw)
    if session_id == 0:
        raise RemediationError(
            "Session 0 is the Windows services session — nobody is signed into it."
        )
    if session_id > 65535:
        raise RemediationError("That is not a valid Windows session id.")
    return str(session_id)


def _validate_message(value: Any) -> str:
    """The text of a message box shown on someone's desktop.

    Control characters are stripped rather than rejected. They cannot do harm here — the
    destination is WTSSendMessage, a native dialog, not a shell or a browser — but a stray
    \\r\\n pasted from a ticket renders as a blank line in a small box, and a NUL truncates
    the message at the Win32 boundary without telling anyone it did.
    """
    text = value if isinstance(value, str) else ""
    text = "".join(c for c in text if c == "\n" or c >= " ").strip()
    if not text:
        raise RemediationError("A message is required — an empty box tells the user nothing.")
    if len(text) > 1000:
        raise RemediationError(
            "Message is too long (1000 characters). A dialog nobody can read past the edge "
            "of the screen is worse than a shorter one."
        )
    return text


def _validate_kb_article_id(value: Any) -> str:
    """Normalize a KB article id to the canonical 'KB<digits>' form. Rejects anything else so
    the value handed to the agent's Windows Update search can never be an injection vector."""
    raw = str(value or "").strip().upper()
    digits = raw[2:] if raw.startswith("KB") else raw
    # isascii() guards against Unicode digit characters (e.g. superscripts) slipping through.
    if not (digits.isascii() and digits.isdigit()) or not (5 <= len(digits) <= 8):
        raise RemediationError(
            f"'{value}' is not a valid Windows Update KB id (expected e.g. KB5034123)."
        )
    return "KB" + digits


# Friendly, outcome-focused lines the assistant shows the user after a fix runs — the point is
# reassurance ("it's fixed"), not the mechanics ("I restarted the service").
# What was actually done, in one line the user can follow.
#
# These used to say things like "That's back up and running", which tells the user nothing
# they didn't already know and reads like an evasion. Naming the mechanism — the process, the
# folder, the cache — is what makes the fix legible: the user learns what changed on their
# machine, and a technical colleague can sanity-check it. Kept to a single sentence; the
# agent's own output (e.g. "Freed 2.1 GB") is appended separately when it has something
# concrete to add.
_TECHNICAL_OUTCOME: dict[str, str] = {
    "restart_explorer":
        "Restarted explorer.exe — the Windows shell that draws your desktop, taskbar and File Explorer.",
    "restart_outlook":
        "Restarted Outlook's process, which rebuilds its Exchange connection and clears its in-memory state.",
    "restart_teams": "Restarted the Teams process, clearing the cached session state it was stuck on.",
    "restart_zoom": "Restarted the Zoom process, clearing the cached session state it was stuck on.",
    "restart_chrome": "Restarted Chrome, releasing the memory its tabs and extensions were holding.",
    "restart_edge": "Restarted Edge, releasing the memory its tabs and extensions were holding.",
    "restart_application": "Restarted the application's process, clearing whatever state it was stuck in.",
    "flush_dns":
        "Flushed the DNS resolver cache, so your PC re-queries the DNS server instead of reusing stale records.",
    "clear_temp":
        "Emptied your user temp folder (%TEMP%) — Windows and your apps recreate whatever they still need.",
    "clear_system_temp":
        "Cleared C:\\Windows\\Temp, the machine-wide temp folder only an elevated process can reach.",
    "clear_browser_cache":
        "Deleted the browser's cached files, so pages are fetched fresh instead of served from disk.",
    "restart_network_adapter":
        "Disabled and re-enabled the network adapter, renewing its DHCP lease and resetting the link.",
    "restart_service": "Stopped and restarted the Windows service, clearing its in-memory state.",
    "create_outlook_rule":
        "Created the rule server-side on your mailbox, so it applies wherever you read your mail.",
    "office_repair":
        "Ran Office's built-in repair, which re-registers its components and replaces damaged files.",
    "network_reset":
        "Reset the TCP/IP stack and Winsock catalog, clearing the corrupted network configuration.",
    "windows_update_install":
        "Installed the pending updates through the Windows Update service.",
}


# Which roles may approve a task of a given tier. AUTOMATIC never reaches approval.
_APPROVER_ROLES: dict[RemediationTier, set[UserRole]] = {
    RemediationTier.APPROVAL_REQUIRED: {UserRole.ADMIN, UserRole.TECHNICIAN},
    RemediationTier.ADMIN_ONLY: {UserRole.ADMIN},
}


class RemediationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = RemediationRepository(session)
        self.devices = DeviceRepository(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)
        self.settings = SettingsService(session)

    async def _assert_may_approve(self, actor: User, tier: RemediationTier) -> None:
        """Raise unless this user may clear an action at this trust tier.

        Shared by approve_task and by inline approval on create, so the rule is defined once.
        AUTOMATIC never reaches approval, so it has no entry and nobody can "approve" it into
        existence at a higher trust level than it was granted.
        """
        allowed = _APPROVER_ROLES.get(tier, set())
        # Org policy can tighten the standard tier to admin-only approval.
        if tier is RemediationTier.APPROVAL_REQUIRED:
            org_settings = await self.settings.ensure(actor.org_id)
            if org_settings.require_admin_for_approval_tier:
                allowed = {UserRole.ADMIN}
        if tier is not RemediationTier.AUTOMATIC and actor.role not in allowed:
            # A technician cannot approve an admin-only action; a user cannot approve anything.
            raise RemediationError("Your role cannot approve a task at this trust tier.")

    # -- Creation --------------------------------------------------------------

    async def create_task(
        self,
        *,
        org_id: uuid.UUID,
        device: Device,
        action_id: str,
        params: dict[str, Any] | None,
        reason: str,
        source: RemediationSource,
        actor_user_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None = None,
        approver: User | None = None,
    ) -> RemediationTask:
        """Queue a remediation.

        ``approver`` is for flows where the caller IS the approver — someone who chose this
        exact action in the portal and clicked Run. The task is approved in the same step, so
        it never sits pending: previously the portal created and then approved in two calls,
        which raised an "Approval needed" notification for something approved milliseconds
        later, left the approval queue permanently empty, and stranded the task as pending
        forever if the second call was refused.

        Passing an approver does NOT bypass the tier rules — they are checked here, and a
        caller who may not approve at this tier is rejected before anything is created.
        """
        action = get_action(action_id)
        if action is None:
            raise RemediationError(f"Unknown remediation action '{action_id}'.")
        params = self._validate_params(action_id, params)
        # Checked here rather than in _validate_params because the answer depends on the
        # organization's own policy list, which is a database read, not a constant.
        if "app_name" in action.params:
            params["app_name"] = await self._validate_uninstall_target(
                org_id, params.get("app_name"), source
            )

        # Secure offboarding is a Professional feature. Checked here rather than by hiding
        # the button, because the button is not the security boundary.
        if action_id in _LOCKDOWN_ACTIONS and not await self._org_has(org_id, LOCKDOWN):
            raise RemediationError(
                "Secure offboarding and device lock-down are part of the Professional plan."
            )

        # Check the approver's authority BEFORE creating anything, so a refusal leaves no
        # half-finished task behind.
        if approver is not None:
            await self._assert_may_approve(approver, action.tier)

        # Don't queue the same work twice on one device. A long action (a Windows Update
        # install runs for tens of minutes) shows no progress while it runs, so an operator
        # who sees nothing happen clicks again — three identical update installs were queued
        # on one machine this way, and the agent runs them one after another, tripling how
        # long the device is tied up doing work it had already been asked to do once.
        existing = await self.repo.find_in_flight(
            device_id=device.id,
            action_id=action_id,
            params=params,
            not_before=utcnow() - _IN_FLIGHT_WINDOW,
        )
        if existing is not None:
            raise AlreadyQueuedError(
                f"{action.label} is already {_STATE_WORDS[existing.status]} on {device.hostname}.",
                existing,
            )

        # Blast-radius / fleet circuit breaker: count recent remediations for the org.
        window_start = utcnow() - timedelta(seconds=settings.remediation_burst_window_seconds)
        recent = await self.repo.count_recent_for_org(org_id, window_start)
        if recent >= settings.remediation_hard_burst:
            raise RemediationError(
                "Fleet safety limit reached: too many remediations were requested in a short "
                "window. New actions are paused — please review activity and try again shortly."
            )
        breaker_tripped = recent >= settings.remediation_auto_approve_burst

        # Tier drives the initial status: automatic is pre-approved; everything else
        # waits for a human. This is enforced here in the service, never by the client.
        # The org-level automation kill-switch — and the circuit breaker above — can
        # force even automatic actions to wait for a human.
        org_settings = await self.settings.ensure(org_id)

        # The Essential / Professional line, and the only place it can honestly be drawn.
        # Essential is sold as "the AI tells you what's wrong"; Professional as "the AI fixes
        # it on its own". So an Essential org still gets every action — a human just clears
        # each one. Nothing is hidden and nothing stops working; the unattended part is what
        # is being paid for.
        can_act_unattended = await self._org_has(org_id, AI_ACT)

        auto_ok = (
            action.tier is RemediationTier.AUTOMATIC
            and org_settings.auto_approve_automatic
            and can_act_unattended
            and not breaker_tripped
        )
        # An explicit approver clears it immediately — they have already made the decision
        # this status exists to wait for. The circuit breaker still wins: if the fleet limit
        # tripped, a human deciding one action shouldn't unleash the rest.
        if approver is not None and not breaker_tripped:
            status = RemediationStatus.APPROVED
        else:
            status = RemediationStatus.APPROVED if auto_ok else RemediationStatus.PENDING_APPROVAL

        task = await self.repo.add(
            RemediationTask(
                org_id=org_id,
                device_id=device.id,
                action_id=action_id,
                params=params or None,
                tier=action.tier.value,
                status=status,
                reason=reason,
                source=source,
                requested_by_user_id=actor_user_id,
                conversation_id=conversation_id,
                approved_by_user_id=approver.id if approver is not None else None,
            )
        )
        await self.audit.record(
            org_id=org_id,
            actor_id=actor_user_id,
            action="remediation.create",
            target_type="remediation_task",
            target_id=str(task.id),
            detail={"action": action_id, "tier": action.tier.value, "status": status.value,
                    "device": device.hostname, "source": source.value},
        )
        # Record the approval as its own audit entry so "who cleared this" is answerable
        # from the log alone, exactly as it is when someone approves from the queue.
        if approver is not None and status is RemediationStatus.APPROVED:
            await self.audit.record(
                org_id=org_id,
                actor_id=approver.id,
                action="remediation.approve",
                target_type="remediation_task",
                target_id=str(task.id),
                detail={"action": action_id, "tier": action.tier.value, "inline": True},
            )
        if status is RemediationStatus.PENDING_APPROVAL:
            approver_label = "an admin" if action.tier is RemediationTier.ADMIN_ONLY else "a technician or admin"
            await self.notifications.notify(
                org_id=org_id,
                category=NotificationCategory.REMEDIATION,
                severity=NotificationSeverity.WARNING,
                title="Approval needed",
                message=f"{action.label} on {device.hostname} needs approval from {approver_label}.",
                link="/self-healing",
            )
        await self.session.commit()
        return task

    async def _validate_uninstall_target(
        self, org_id: uuid.UUID, value: Any, source: RemediationSource
    ) -> str:
        """Which applications may be uninstalled, and by whom.

        Two different callers ask for this, and they do not deserve the same latitude:

        * The AI engine (``source=ASSISTANT``) may only remove software THIS organization
          wrote down as restricted. Every other action in the registry is constrained by a
          fixed allowlist; this one cannot be, because the whole point is to remove whatever
          the customer decided they do not want. Their own policy list is that allowlist, so
          the model can never propose removing something nobody wrote down.
        * An admin in the portal (``source=USER``) may remove anything not protected. They
          are looking at the device's own software inventory, they picked one row, they typed
          a reason, and the action is ADMIN_ONLY so only an admin can approve it. Requiring
          them to first add the app to a policy list would mean editing org-wide policy to
          perform a one-off removal on one machine — which pollutes the policy list and
          teaches people to add entries they intend to delete afterwards.

        What NEITHER may reach is UNINSTALL_NEVER. It is checked first and applies to both,
        so no organization can reach protected software by adding it to their own list, and
        no portal session can strip a machine's defences.
        """
        from sqlalchemy import select

        from app.models import BannedSoftware
        from app.services.remediation.actions import UNINSTALL_NEVER

        name = (value or "").strip() if isinstance(value, str) else ""
        if not name:
            raise RemediationError("An application name is required to uninstall it.")
        if len(name) > 300:
            raise RemediationError("Application name is too long.")

        lowered = name.lower()
        for protected in UNINSTALL_NEVER:
            if protected in lowered:
                raise RemediationError(
                    f"'{name}' is protected and can never be uninstalled by ASTRA."
                )

        if source is not RemediationSource.ASSISTANT:
            return name

        patterns = (await self.session.execute(
            select(BannedSoftware.pattern).where(BannedSoftware.org_id == org_id)
        )).scalars().all()
        if not any(p and p in lowered for p in patterns):
            raise RemediationError(
                f"'{name}' is not on this organization's restricted-software list. "
                "ASTRA only proposes removing software the organization has restricted — "
                "add it there first, or have an admin remove it from the device's Software tab."
            )
        return name

    def _validate_params(
        self, action_id: str, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        action = ACTIONS[action_id]
        params = params or {}
        # Only the parameters the action declares are accepted.
        extra = set(params) - set(action.params)
        if extra:
            raise RemediationError(f"Unexpected parameter(s) for {action_id}: {sorted(extra)}")
        if "service_name" in action.params:
            name = params.get("service_name")
            if name not in SAFE_SERVICES:
                raise RemediationError(
                    f"Service '{name}' is not on the allowlist of restartable services."
                )
        if "process_name" in action.params:
            name = params.get("process_name") or ""
            # Case-insensitive allowlist check — the agent will match the process the same way.
            if name.lower() not in {p.lower() for p in SAFE_APP_PROCESSES}:
                raise RemediationError(
                    f"Application '{name}' is not on the allowlist of restartable applications."
                )
        if "from_address" in action.params:
            params["from_address"] = _validate_email(params.get("from_address"))
        if "folder_name" in action.params:
            params["folder_name"] = _validate_folder_name(params.get("folder_name"))
        if "kb_article_id" in action.params and params.get("kb_article_id"):
            params["kb_article_id"] = _validate_kb_article_id(params["kb_article_id"])
        if "username" in action.params:
            params["username"] = _validate_username(params.get("username"))
        if "session_id" in action.params:
            params["session_id"] = _validate_session_id(params.get("session_id"))
        if "message" in action.params:
            params["message"] = _validate_message(params.get("message"))
        if "timezone_id" in action.params:
            params["timezone_id"] = _validate_timezone(params.get("timezone_id"))
        if "printer_path" in action.params:
            params["printer_path"] = _validate_printer_path(params.get("printer_path"))
        return params

    # -- Approval workflow (portal staff) --------------------------------------

    async def approve_task(self, *, actor: User, task_id: uuid.UUID) -> RemediationTask:
        task = await self._get_owned(actor.org_id, task_id)
        if task.status is not RemediationStatus.PENDING_APPROVAL:
            raise ConflictError("Only a pending task can be approved.")

        await self._assert_may_approve(actor, RemediationTier(task.tier))

        task.status = RemediationStatus.APPROVED
        task.approved_by_user_id = actor.id
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="remediation.approve",
            target_type="remediation_task",
            target_id=str(task.id),
            detail={"action": task.action_id, "tier": task.tier},
        )
        await self.session.commit()
        return task

    async def reject_task(self, *, actor: User, task_id: uuid.UUID) -> RemediationTask:
        task = await self._get_owned(actor.org_id, task_id)
        if task.status is not RemediationStatus.PENDING_APPROVAL:
            raise ConflictError("Only a pending task can be rejected.")
        task.status = RemediationStatus.REJECTED
        task.approved_by_user_id = actor.id
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="remediation.reject",
            target_type="remediation_task",
            target_id=str(task.id),
        )
        await self.session.commit()
        return task

    async def _org_has(self, org_id: uuid.UUID, feature: str) -> bool:
        from app.models import Organization
        from app.services.entitlements import features_for

        org = await self.session.get(Organization, org_id)
        if org is None:
            return True   # unknown org: don't let a lookup miss disable someone's product
        return feature in features_for(org.plan, org.entitlement_overrides)

    async def list_for_org(self, *, actor: User) -> list[RemediationTask]:
        return await self.repo.list_by_org(actor.org_id)

    async def list_page(
        self,
        *,
        actor: User,
        device_id: uuid.UUID | None = None,
        status: list[RemediationStatus] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RemediationTask], int]:
        return await self.repo.list_page(
            actor.org_id, device_id=device_id, status=status, offset=offset, limit=limit
        )

    # -- Agent-facing (device executes approved work) --------------------------

    async def claim_for_device(
        self, *, device: Device, context: str = "user"
    ) -> list[RemediationTask]:
        """Return approved tasks this agent process is allowed to run, and mark them
        dispatched. ``context`` ("user" or "system") selects only the tasks whose action
        runs in that process, so the user-session Tray and the elevated Service never claim
        each other's work. An unknown context is treated as "user" (the safe default a
        legacy agent that sends no context param falls into)."""
        if context != "system":
            context = "user"
        tasks = await self.repo.list_approved_for_device(device.id)
        claimed: list[RemediationTask] = []
        for task in tasks:
            action = get_action(task.action_id)
            task_context = action.execution_context if action else "user"
            if task_context != context:
                continue
            task.status = RemediationStatus.DISPATCHED
            claimed.append(task)

            # Tell the user their fix has actually STARTED, if it came from a device chat.
            #
            # This is not filler: "approved and queued" and "running on your PC right now" are
            # genuinely different states, and until now only the second one was ever visible —
            # the chat went quiet between "I'll do that now" and "✅ All done". That gap is the
            # agent's poll interval, so it grows as polling is made less frequent to cut
            # traffic. Posting on dispatch keeps the user informed without adding a request:
            # the tray refreshes history every few seconds and picks this up on its own.
            if task.conversation_id is not None:
                action_label = action.label.lower() if action else "that"
                self.session.add(
                    Message(
                        conversation_id=task.conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=f"🔧 Working on it now — running {action_label} on your PC. "
                                "This usually takes a few moments.",
                    )
                )
        await self.session.commit()
        return claimed

    async def record_result(
        self, *, device: Device, task_id: uuid.UUID, success: bool, output: str
    ) -> RemediationTask:
        task = await self.repo.get(task_id)
        if task is None or task.device_id != device.id:
            raise NotFoundError("Remediation task not found")
        if task.status is not RemediationStatus.DISPATCHED:
            raise ConflictError("Task is not awaiting a result.")
        task.status = RemediationStatus.SUCCEEDED if success else RemediationStatus.FAILED
        task.result = {"output": output[:4000]}
        task.completed_at = utcnow()
        await self.audit.record(
            org_id=device.org_id,
            actor_id=None,
            action="remediation.result",
            target_type="remediation_task",
            target_id=str(task.id),
            detail={"action": task.action_id, "success": success},
        )
        action = get_action(task.action_id)
        label = action.label if action else task.action_id
        if not success:
            await self.notifications.notify(
                org_id=device.org_id,
                category=NotificationCategory.REMEDIATION,
                severity=NotificationSeverity.CRITICAL,
                title="Remediation failed",
                message=f"{label} failed on {device.hostname}.",
                link="/self-healing",
            )

        # Fold the outcome into the knowledge base. Only chat-originated fixes carry a
        # symptom in the user's own words, which is the half of a runbook that can't be
        # reconstructed later — the action id was always in the task row, the complaint
        # that led to it was not.
        # from_llm, not just ASSISTANT: the built-in keyword rules also create tasks marked
        # ASSISTANT, and there is nothing to learn from those — the rule already knew the
        # answer, so writing a runbook for it would fill the knowledge base with things the
        # system could always do, and bury the hand-written ones under them.
        if (
            task.conversation_id is not None
            and task.source is RemediationSource.ASSISTANT
            and task.from_llm
        ):
            await self._learn_from(task, label, success)

        # If this fix was started from a device chat, post the real outcome back into
        # that conversation so the user sees "✅ done" / "⚠️ couldn't" after it runs.
        if task.conversation_id is not None:
            snippet = (output or "").strip()
            if success:
                # State what was done, then the agent's own measurement if it reported one
                # ("Freed 2.1 GB"). That number was previously computed, sent, and thrown
                # away — it is the most concrete evidence the fix did anything, and the
                # difference between a claim and a result.
                text = f"✅ Done. {_TECHNICAL_OUTCOME.get(task.action_id, '')}".rstrip()
                detail = snippet.splitlines()[0].strip() if snippet else ""
                if detail and detail.lower() not in text.lower():
                    text += f"\n\n{detail[:200]}"
                text += "\n\nTell me if it's still not right and I'll dig further."
            else:
                text = "⚠️ I wasn't able to finish that one automatically."
                if snippet:
                    text += f" {snippet[:400]}"
                # A failure arrives asynchronously — the user may have closed the chat
                # minutes ago. So the offer is posted into the conversation rather than
                # waiting for a turn that may never come, and their reply whenever it
                # arrives is the consent. Falls back to the old wording when the org has
                # no helpdesk connected, which is the truth in that case.
                offer = await self._offer_escalation(task, label)
                text += f" {offer}" if offer else \
                    " I've flagged it for your IT team to take a look."
            self.session.add(
                Message(
                    conversation_id=task.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=text,
                )
            )
        await self.session.commit()
        return task

    async def _offer_escalation(self, task: RemediationTask, label: str) -> str | None:
        """Offer to raise a ticket for a fix that just failed, or None if we can't.

        Never raises: the agent is reporting an outcome that already happened on a real
        machine, and that record must survive anything going wrong here. Returns None when
        the org has no helpdesk, when we cannot name a requester, or when a ticket already
        covers this — the caller then falls back to the plain "flagged for IT" wording.
        """
        from app.services.support import attempts, factory, requester
        from app.services.support.escalation import EscalationService

        try:
            connector = await factory.build_connector(self.session, task.org_id)
            if connector is None:
                return None
            who = await requester.resolve(
                self.session, org_id=task.org_id,
                conversation_id=task.conversation_id, device_id=task.device_id,
            )
            if who is None:
                return None

            # The complaint this fix was answering, in the user's own words — the last
            # thing they said before it started, not the first thing in the chat.
            problem = await attempts.complaint_before(
                self.session, task.conversation_id, task.created_at
            )
            if not problem:
                return None

            # Shared with the chat-driven path so the two ways a ticket gets offered
            # describe the same situation the same way. This task is already in the session
            # with its final status, so it appears in the attempts without being added here.
            dossier = await attempts.build_dossier(
                self.session, conversation_id=task.conversation_id,
                device_id=task.device_id, problem=problem,
            )
            if dossier is None:
                return None

            _, message = await EscalationService(
                self.session, connector=connector
            ).offer(
                org_id=task.org_id, conversation_id=task.conversation_id,
                device_id=task.device_id, user_id=who.user_id,
                dossier=dossier, action_id=task.action_id,
            )
            return message
        except Exception:  # noqa: BLE001 — never lose a real outcome over an offer
            logger.exception("Could not offer escalation for remediation %s", task.id)
            return None

    async def _learn_from(self, task: RemediationTask, label: str, success: bool) -> None:
        """Record what this fix taught us, without ever putting the result at risk.

        Two things are learned here, and this is the right place for both because it is the
        only place that knows the fix actually WORKED. The device has run it and said so.

          - the auto-apply store, so the next person to describe this problem gets the fix
            straight away and the model is never called;
          - the knowledge article, which needs the same outcome repeatedly before it will
            publish anything.

        The agent is reporting something that has already happened on a real machine. If
        anything here goes wrong — a missing conversation, an embedding that throws — the
        task result must still be written, so this swallows its own failures rather than
        propagating them up the agent's request.
        """
        from sqlalchemy import select

        from app.services.ai.knowledge import KnowledgeBaseService
        from app.services.ai.learned import LearnedFixStore

        try:
            # The complaint that led to this fix: the last thing the user said before the
            # task was created. Not the first message — a chat can wander through several
            # problems, and the one being fixed is the most recent one raised.
            result = await self.session.execute(
                select(Message.content)
                .where(
                    Message.conversation_id == task.conversation_id,
                    Message.role == MessageRole.USER,
                    Message.created_at <= task.created_at,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            symptom = result.scalar_one_or_none()
            if not symptom:
                return

            # Only a fix that worked earns a place in the auto-apply store, because a hit
            # there skips the model entirely. A failure teaches the knowledge article
            # something — its success rate is how it knows to stop recommending itself —
            # but it must never become an answer handed out on its own.
            if success:
                await LearnedFixStore(self.session).learn(
                    org_id=task.org_id, query=symptom[:1000],
                    action_id=task.action_id, params=task.params,
                )

            await KnowledgeBaseService(self.session).learn_from_fix(
                org_id=task.org_id,
                action_id=task.action_id,
                action_label=label,
                params=task.params,
                symptom=symptom[:300],
                success=success,
            )
        except Exception:  # noqa: BLE001 — never fail a real outcome over bookkeeping
            logger.exception("Could not learn from remediation %s", task.id)

    async def _get_owned(self, org_id: uuid.UUID, task_id: uuid.UUID) -> RemediationTask:
        task = await self.repo.get(task_id)
        if task is None or task.org_id != org_id:
            raise NotFoundError("Remediation task not found")
        return task
