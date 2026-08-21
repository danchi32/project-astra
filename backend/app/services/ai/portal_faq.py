"""What the in-portal assistant knows without being told — ASTRA's own support manual.

The portal bot has three sources: the organization's own knowledge base, ASTRA's published
help articles, and this. This is the one that is always there. A fresh organization has an
empty knowledge base and an operator may have published nothing yet, and "I couldn't find
anything about that" is a poor first impression from the help widget of a product the
person has just bought.

It is also the source that needs no API key. Retrieval and these answers are ordinary
Python, so when the model is unreachable the assistant still answers questions about
installing the agent, why a device shows offline, who can approve a fix, or what the
compliance score means — it just quotes the written answer instead of composing one.

Everything here is checked against the code it describes: role names from `UserRole`, the
offline threshold from `schemas.devices.ONLINE_THRESHOLD`, tiers from
`services.remediation.actions`, page names from the portal sidebar, network rules from
docs/NETWORK-REQUIREMENTS.md. When one of those changes, this changes with it.
"""
from app.services.ai.faq import FaqEntry

#: Sent on every portal question, so the assistant can answer about the product itself
#: even when retrieval finds nothing. Complements `public_faq.PRODUCT_BRIEF`, which covers
#: what ASTRA is and what it costs; this one covers using it.
PORTAL_BRIEF = """# Using ASTRA — orientation for the in-portal assistant

## The portal, page by page
Dashboard (fleet health at a glance) · Devices (every enrolled machine, its telemetry and
history) · Compliance (security-posture scoring) · Fleet Issues (the same fault correlated
across devices, and mass remediation) · Users · Knowledge Base (the organization's own
runbooks) · Self Healing (the remediation queue and approvals) · Reports · Audit Logs ·
Billing (admins) · Get installer · Notifications · Help & Support (guides, the assistant,
and requests to the ASTRA team) · Settings.

## Roles
- admin — everything, including billing, users, settings, and admin-only fixes.
- technician — day-to-day operations: devices, remediation, knowledge, reports. Can
  approve approval-required fixes, but not admin-only ones.
- user — an ordinary employee: their own devices and the assistant.

## Devices and the agent
The agent is a Windows service plus a tray app. It sends a heartbeat every 60 seconds; a
device that has not been heard from for 3 minutes is shown offline. It needs outbound
HTTPS (443) to api.astra.technomateai.com and nothing inbound; it uses the corporate proxy
automatically. Enrolment uses a token the portal issues, from Get installer.

## Fixes and approval
Three tiers, enforced in the backend:
- automatic — restart Explorer / Outlook / Teams / Zoom / Chrome / Edge and other
  allowlisted apps, flush DNS, clear temp files, restart a network adapter. Runs by itself.
- approval-required — Office repair, driver update, network reset. Waits in Self Healing;
  a technician or an admin approves it.
- admin-only — registry work, Windows Update component reset, account offboarding. Only an
  admin can approve.
A fix pushed by hand from a device page is approved as it is pushed. The queue on Self
Healing is for what the AI proposed and for anything above the automatic tier.

## What the assistant in the portal can and cannot do
It answers from documentation. It cannot restart anything, run a fix, change a setting or
open a ticket. Fixes are run from the device's page in the portal, or by asking ASTRA from
the tray app on the machine itself, which does act.
"""


PORTAL_FAQ: tuple[FaqEntry, ...] = (
    # -- orientation -----------------------------------------------------------
    FaqEntry(
        question="What can you help me with?",
        answer=(
            "Anything about running ASTRA: installing and enrolling the agent, why a device "
            "is offline, telemetry, self-healing and approvals, patching, compliance, users "
            "and roles, billing and seats, reports and audit, and your organization's own "
            "runbooks. I answer from the documentation — I can't run a fix myself. For that, "
            "use the device's page in the portal, or ask ASTRA from the tray app on the "
            "machine, which can act."
        ),
        keywords=("hello", "hi", "hey", "assistant", "bot", "capabilities", "you", "there",
                  "guide", "ask", "topics"),
    ),
    # -- installing and enrolling ---------------------------------------------
    FaqEntry(
        question="How do I install the ASTRA agent on a device?",
        answer=(
            "Open Get installer in the sidebar and download the .exe installer — it already "
            "carries your organization's enrolment ticket, so there is nothing to type in. "
            "Run it on the Windows machine as an administrator. The agent installs as a "
            "service plus a tray app, enrols itself, and the device appears in Devices "
            "within about a minute. A portable installer is available on the same page for "
            "machines where you would rather not run an .exe."
        ),
        keywords=("install", "installer", "setup", "enrol", "enroll", "enrolment",
                  "enrollment", "add", "device", "agent", "download", "onboard", "new",
                  "machine", "exe"),
    ),
    FaqEntry(
        question="How do I roll the agent out to a whole fleet?",
        answer=(
            "Use the same installer from Get installer and push it through Intune, Group "
            "Policy or whatever software distribution you already run. Devices enrol as they "
            "receive it and appear in Devices as they check in. The installer's enrolment "
            "ticket expires, so build a fresh one for each rollout wave rather than reusing "
            "an old file, and rotate the enrolment key from the same page if one leaks."
        ),
        keywords=("fleet", "bulk", "mass", "intune", "gpo", "group policy", "sccm",
                  "deployment", "rollout", "many", "silent", "unattended", "script"),
    ),
    FaqEntry(
        question="A device is not showing up after installing the agent",
        answer=(
            "Three things account for almost all of these. First, the installer's enrolment "
            "ticket may have expired — download a fresh installer from Get installer. Second, "
            "the machine may not be able to reach the service: it needs outbound HTTPS on 443 "
            "to api.astra.technomateai.com. Third, endpoint protection may have quarantined "
            "the agent — check your antivirus quarantine for AstraAgent, and add an exclusion "
            "if it is there. On the machine itself, check that the ASTRA service is running "
            "in services.msc."
        ),
        keywords=("missing", "appear", "appearing", "showing", "enrol", "enroll", "failed",
                  "install", "not", "visible", "register", "stuck", "pending"),
    ),
    FaqEntry(
        question="Why does a device show as offline?",
        answer=(
            "The agent sends a heartbeat every 60 seconds, and a device that has not been "
            "heard from for 3 minutes is marked offline. So a device shows offline when it is "
            "switched off, asleep, off the network, or when the agent service has stopped. If "
            "the machine is definitely on and connected, check that the ASTRA service is "
            "running on it, and that outbound HTTPS to api.astra.technomateai.com is not "
            "being blocked by a firewall or a proxy."
        ),
        keywords=("offline", "online", "disconnected", "heartbeat", "reporting", "stale",
                  "grey", "gray", "last seen", "status", "unreachable"),
    ),
    FaqEntry(
        question="What does the agent need on our network?",
        answer=(
            "Outbound HTTPS on port 443 only — no inbound ports at all. It needs "
            "api.astra.technomateai.com for enrolment, heartbeat, telemetry, remediation and "
            "chat, plus github.com and objects.githubusercontent.com for signed auto-updates, "
            "and aka.ms / dotnet.microsoft.com once if the .NET 8 runtime is missing at "
            "install. It picks up the corporate proxy automatically (install-time -ProxyUrl, "
            "then HTTPS_PROXY, then the machine WinHTTP proxy) and works through TLS "
            "inspection, because it validates against the Windows machine certificate store "
            "and does not pin certificates."
        ),
        keywords=("firewall", "network", "proxy", "port", "url", "allowlist", "whitelist",
                  "blocked", "tls", "ssl", "inspection", "outbound", "domains", "connect"),
    ),
    FaqEntry(
        question="Our antivirus quarantined the ASTRA agent",
        answer=(
            "That is a false positive, most often Microsoft Defender flagging "
            "AstraAgent.Service.dll. Restore it from quarantine and add an exclusion for the "
            "ASTRA agent's install folder through your endpoint-protection policy (in Intune, "
            "a Defender exclusion for the folder). Until you do, the service will be removed "
            "again and the device will keep going offline."
        ),
        keywords=("antivirus", "defender", "quarantine", "virus", "malware", "blocked",
                  "edr", "false positive", "threat", "removed", "deleted", "exclusion"),
    ),
    FaqEntry(
        question="How do I remove the agent or retire a device?",
        answer=(
            "Get installer also provides the uninstaller — run it on the machine to remove "
            "the service and the tray app. Once a device stops reporting you can archive it "
            "from Devices so it no longer counts against your seats or clutters the fleet "
            "view; its history and audit trail are kept."
        ),
        keywords=("uninstall", "remove", "delete", "retire", "archive", "decommission",
                  "old", "replace", "seat", "cleanup"),
    ),
    # -- telemetry and devices -------------------------------------------------
    FaqEntry(
        question="What data does the agent collect from a device?",
        answer=(
            "Operational telemetry: CPU, RAM and disk usage, Windows event-log errors and "
            "warnings, installed and running applications, services, and Windows Update "
            "status — the evidence needed to diagnose a fault. It is not employee "
            "monitoring: no keystrokes, no screen capture, no browsing history. Everything "
            "collected is visible to you on the device's page."
        ),
        keywords=("telemetry", "data", "collect", "privacy", "monitor", "monitoring",
                  "keystroke", "screen", "spy", "surveillance", "gdpr", "employee",
                  "personal", "gather"),
    ),
    FaqEntry(
        question="What can I see on a device's page?",
        answer=(
            "Its live telemetry (CPU, RAM, disk), hardware and software inventory, recent "
            "Windows event-log errors, services, Windows Update status, the remediation "
            "history for that machine, and the actions you can push to it. It is the page to "
            "open when somebody reports a problem with one specific machine."
        ),
        keywords=("device", "detail", "page", "inventory", "hardware", "specs", "software",
                  "history", "events", "logs", "see", "view"),
    ),
    # -- self-healing ----------------------------------------------------------
    FaqEntry(
        question="How does self-healing work?",
        answer=(
            "ASTRA gathers evidence before it acts: it reads the device's telemetry and "
            "event log, checks the knowledge base, and only then proposes a fix from an "
            "allowlist. Where the fix lands decides what happens next — automatic fixes run "
            "straight away, approval-required ones wait in Self Healing for a technician or "
            "admin, and admin-only ones wait for an admin. Once the agent runs it, the result "
            "comes back to the same place, and a fix that repeatedly works is folded into the "
            "knowledge base."
        ),
        keywords=("self healing", "selfhealing", "remediation", "automatic", "fix", "heal",
                  "repair", "resolve", "automation", "works"),
    ),
    FaqEntry(
        question="Where do I approve a fix, and who is allowed to?",
        answer=(
            "Self Healing in the sidebar holds the queue. Approval-required fixes — Office "
            "repair, driver update, network reset — can be approved by a technician or an "
            "admin. Admin-only fixes — registry work, Windows Update component reset, account "
            "offboarding — need an admin. If the Approve button returns a permission error, "
            "the fix is above your role's tier."
        ),
        keywords=("approve", "approval", "pending", "queue", "authorise", "authorize",
                  "permission", "reject", "who", "waiting", "tier", "allowed"),
    ),
    FaqEntry(
        question="Which fixes run automatically and which need approval?",
        answer=(
            "Automatic: restarting Explorer, Outlook, Teams, Zoom, Chrome, Edge and other "
            "allowlisted applications, flushing DNS, clearing temp files, restarting a "
            "network adapter. Approval-required: Office repair, driver update, network reset. "
            "Admin-only: registry changes, Windows Update component reset, account "
            "offboarding. The tier is enforced in the backend, so nothing — including the AI "
            "— can run an action above the tier it was given."
        ),
        keywords=("tier", "tiers", "automatic", "approval", "admin", "list", "actions",
                  "allowlist", "what", "safe", "risky", "categories"),
    ),
    FaqEntry(
        question="Can I run a fix myself without waiting for the AI?",
        answer=(
            "Yes. Open the device in Devices and push the action from there. A fix you push "
            "by hand is approved as you push it, so it does not sit in the queue — the queue "
            "is for what the AI proposed and for anything above the automatic tier."
        ),
        keywords=("manual", "myself", "push", "run", "trigger", "force", "now", "directly",
                  "without", "restart"),
    ),
    FaqEntry(
        question="A fix failed — what now?",
        answer=(
            "The result and the agent's output are recorded against the device and in the "
            "remediation history, so start there: it usually says whether the machine was "
            "offline, the app was not installed, or the action genuinely did not work. A "
            "failure also counts against that fix in the knowledge base, so advice whose "
            "success rate falls stops being recommended. If it keeps failing, raise a request "
            "under Help & Support and include the device name."
        ),
        keywords=("failed", "failure", "error", "didn't", "not work", "unsuccessful",
                  "retry", "again", "broken", "result"),
    ),
    FaqEntry(
        question="How do I push Windows updates?",
        answer=(
            "From Telemetry -> Updates on a device, or across the fleet from the admin "
            "panel: pick the devices and push, then watch the rollout status per machine as "
            "it happens. Every push is written to the audit log."
        ),
        keywords=("update", "updates", "patch", "patching", "windows update", "wsus",
                  "security", "install", "rollout", "push"),
    ),
    # -- fleet, compliance, knowledge -----------------------------------------
    FaqEntry(
        question="What is Fleet Issues for?",
        answer=(
            "It links the same fault across many devices — the driver that is failing on "
            "eleven laptops rather than one — and lets you remediate the whole affected group "
            "in one click instead of repeating yourself. It is where to look when several "
            "people report the same thing at once."
        ),
        keywords=("fleet", "issues", "correlation", "pattern", "mass", "group", "many",
                  "widespread", "bulk", "same"),
    ),
    FaqEntry(
        question="What does the compliance score mean?",
        answer=(
            "Compliance scores your fleet's security posture and flags the devices that fall "
            "short — missing updates, unhealthy protection, restricted or unapproved software "
            "found on a machine. It is the page to take to an auditor, and the list to work "
            "down when you want the fleet in a known state."
        ),
        keywords=("compliance", "posture", "score", "security", "audit", "policy",
                  "restricted", "software", "shadow", "risk", "dashboard"),
    ),
    FaqEntry(
        question="What is the Knowledge Base for, and how do I add to it?",
        answer=(
            "It holds your organization's own runbooks — how your VPN is set up, which "
            "printer queue serves which floor — and the assistant answers from them alongside "
            "ASTRA's own guides. Add an article from Knowledge Base in the sidebar. ASTRA "
            "also writes its own: a fix that repeatedly resolves the same symptom is "
            "published automatically, and dropped again if its success rate collapses."
        ),
        keywords=("knowledge", "runbook", "article", "documentation", "kb", "add", "write",
                  "learn", "learned", "publish", "guide"),
    ),
    # -- people, billing, records ---------------------------------------------
    FaqEntry(
        question="How do I add users, and what can each role do?",
        answer=(
            "Users in the sidebar, where an admin can add people in bulk — one per line, with "
            "the role admin, technician or user (it defaults to user). An admin has "
            "everything including billing, users and settings; a technician runs day-to-day "
            "operations and can approve approval-required fixes but not admin-only ones; a "
            "user is an ordinary employee with their own devices and the assistant."
        ),
        keywords=("user", "users", "role", "roles", "permission", "rbac", "admin",
                  "technician", "invite", "add", "team", "staff", "access"),
    ),
    FaqEntry(
        question="How are we billed, and where are the invoices?",
        answer=(
            "By licensed seats, against the devices you have active. Billing in the sidebar "
            "(admins only) shows the plan, the seat count and the invoices. If a subscription "
            "lapses the organization goes read-only rather than dark — you can still see "
            "everything and the agents keep reporting, but changes are blocked until it is "
            "settled, and Billing stays reachable so it can be."
        ),
        keywords=("billing", "invoice", "invoices", "seat", "seats", "licence", "license",
                  "plan", "subscription", "payment", "pay", "renew", "readonly",
                  "read-only", "cost"),
    ),
    FaqEntry(
        question="What is in the audit log?",
        answer=(
            "Every change and every command sent to a device: who did it, what it was, when, "
            "and against which machine — including approvals, pushed fixes, user and settings "
            "changes. Audit Logs in the sidebar. It is the record to reach for after an "
            "incident, and the one an auditor asks for."
        ),
        keywords=("audit", "log", "logs", "history", "trail", "who", "record", "track",
                  "changed", "evidence", "compliance"),
    ),
    FaqEntry(
        question="What reports can I get out of ASTRA?",
        answer=(
            "Reports covers fleet health, issue resolution and compliance — the summaries "
            "worth putting in front of stakeholders rather than raw telemetry. The Expert "
            "plan adds full audit-trail export."
        ),
        keywords=("report", "reports", "export", "csv", "summary", "stakeholder",
                  "management", "download", "statistics", "metrics"),
    ),
    FaqEntry(
        question="How do notifications work?",
        answer=(
            "Notifications tells you when something needs a human: a fix waiting for "
            "approval, a device that has gone quiet, a compliance drop. The bell in the top "
            "bar carries the unread count, and Notifications lists them."
        ),
        keywords=("notification", "notifications", "alert", "alerts", "email", "notify",
                  "bell", "unread", "proactive", "warning"),
    ),
    # -- specific jobs ---------------------------------------------------------
    FaqEntry(
        question="Someone is leaving — how do I lock down their machine?",
        answer=(
            "Secure offboarding disables their local account and forces them out of their "
            "active Windows session in one click, not just at next login, matching the exact "
            "account by its security ID. It is an admin-only action and every lock-down is "
            "audited. Do it before the laptop comes back, not after."
        ),
        keywords=("offboarding", "leaver", "leaving", "resign", "termination", "fired",
                  "disable", "lock", "account", "session", "exit", "employee", "quit"),
    ),
    FaqEntry(
        question="How do I record who has which laptop?",
        answer=(
            "Assets tracks assignment. When you assign a device the employee is emailed to "
            "confirm receipt — sent from your own verified domain once you have set that up "
            "in Settings — and the signed acknowledgement is kept on the asset record. "
            "Archived assets keep their history."
        ),
        keywords=("asset", "assets", "assign", "assignment", "acknowledge", "handover",
                  "custody", "laptop", "who", "inventory", "receipt", "sign"),
    ),
    FaqEntry(
        question="Can ASTRA raise tickets in our helpdesk?",
        answer=(
            "Yes — Freshservice. Connect it under Settings -> Helpdesk. Once it is connected "
            "ASTRA offers to raise a ticket for what it cannot fix itself, with the device's "
            "evidence attached, and only after the user has agreed to it."
        ),
        keywords=("helpdesk", "ticket", "freshservice", "integration", "integrate",
                  "servicenow", "jira", "zendesk", "connect", "itsm", "escalate"),
    ),
    FaqEntry(
        question="How do I send ASTRA's emails from our own domain?",
        answer=(
            "Settings -> Send email as your organization. Enter the domain, add the DNS "
            "records it shows you, and wait for verification. Until then asset "
            "acknowledgement emails go out from ASTRA's own address rather than yours."
        ),
        keywords=("email", "domain", "dns", "spf", "dkim", "verify", "verification",
                  "sender", "from", "branding", "smtp"),
    ),
    FaqEntry(
        question="What can employees do from the tray app?",
        answer=(
            "They describe the problem in plain language — 'Outlook keeps freezing' — and "
            "ASTRA checks that machine's telemetry and event log, then either fixes it or "
            "explains what it found. Anything above the automatic tier is queued for your "
            "team instead of being applied silently, so employees cannot talk it into "
            "something they are not entitled to."
        ),
        keywords=("tray", "employee", "user", "chat", "self service", "desktop", "app",
                  "end user", "staff", "themselves", "assistant"),
    ),
    FaqEntry(
        question="How do I change my password or the look of the portal?",
        answer=(
            "Settings holds your profile, a password change (which signs out your other "
            "sessions but not this one), and Appearance for light, dark or system theme. "
            "Organization-wide options — automation, minimum password length, the enrolment "
            "token lifetime — are on the same page for admins."
        ),
        keywords=("password", "profile", "theme", "dark", "light", "appearance", "account",
                  "change", "name", "settings", "preference"),
    ),
    FaqEntry(
        question="How do I get help from the ASTRA team?",
        answer=(
            "Help & Support -> My requests, where you can raise a request and follow the "
            "replies. Diagnostics are attached server-side, so you do not need to gather "
            "anything first. The Guides tab there is searchable and takes an error code "
            "pasted straight in."
        ),
        keywords=("support", "help", "contact", "request", "ticket", "human", "team",
                  "escalate", "stuck", "problem", "raise", "astra team"),
    ),
    FaqEntry(
        question="Does the agent update itself?",
        answer=(
            "Yes — agents update themselves from signed releases, so you do not have to "
            "redeploy the installer for a new version. That is why github.com and "
            "objects.githubusercontent.com are on the outbound allowlist."
        ),
        keywords=("agent", "update", "upgrade", "version", "auto", "latest", "signed",
                  "release", "redeploy", "maintenance"),
    ),
    # -- the problems people actually report -----------------------------------
    #
    # These overlap with the runbooks `scripts/seed_knowledge.py` writes, and that is on
    # purpose. Those live in the database, are seeded per environment, and are retrieved
    # semantically — all three are things that can be missing or misconfigured. A database
    # article, when there is one, still outranks these; this is the floor, so the widget
    # answers "my printer won't print" on day one of a fresh install with no key, no
    # articles and no aliases. Keep the advice in step with the runbooks.
    FaqEntry(
        question="Outlook will not open, is frozen, or stopped sending",
        answer=(
            "Restarting Outlook clears most of these, and ASTRA can do that automatically — "
            "a background Outlook process is usually still holding the profile. If it fails "
            "again straight after a restart, the install is damaged rather than stuck and it "
            "needs an Office repair, which waits for IT approval and closes every Office app, "
            "so save your work first. Don't repair Office on the first failure."
        ),
        keywords=("outlook", "mail", "email", "inbox", "office", "frozen", "crash",
                  "crashing", "hang", "stuck", "send", "receive", "profile"),
    ),
    FaqEntry(
        question="Teams will not load, sign in, or shows a blank window",
        answer=(
            "Restart Teams — ASTRA can do that automatically. If Teams loads but the "
            "microphone or camera is missing from a call, that is a Windows privacy setting "
            "rather than a Teams fault: allow microphone and camera access under Settings > "
            "Privacy & security. ASTRA cannot change that for you."
        ),
        keywords=("teams", "meeting", "blank", "white", "splash", "sign", "microphone",
                  "camera", "audio", "video", "call", "loading"),
    ),
    FaqEntry(
        question="Printing does not work or the print queue is stuck",
        answer=(
            "A stuck print spooler is the most common cause, and restarting it clears the "
            "queue — ASTRA can do that automatically. If the printer shows offline "
            "afterwards, check that it is powered on and reachable on the network; if only "
            "one application cannot print, restart that application rather than the spooler."
        ),
        keywords=("print", "printer", "printing", "spooler", "queue", "paper", "scan",
                  "jobs", "offline"),
    ),
    FaqEntry(
        question="Wi-Fi keeps dropping or there is no internet",
        answer=(
            "Flushing DNS and restarting the network adapter fix most single-machine cases, "
            "and ASTRA can run both automatically. If several devices in the same office "
            "report it at once, it is the access point or the line rather than the laptops — "
            "check Fleet Issues, which groups the same fault across machines."
        ),
        keywords=("wifi", "wi-fi", "internet", "network", "connection", "dns", "dropping",
                  "disconnect", "offline", "adapter", "vpn", "slow"),
    ),
    FaqEntry(
        question="A computer is very slow",
        answer=(
            "Check the evidence before acting — 'slow' has several causes and the device's "
            "page shows which one. High memory with a browser open is usually tabs; a full "
            "disk is a different fix (clearing temp files, which runs automatically); pegged "
            "CPU with nothing running is often a stuck update. If CPU, memory and disk are "
            "all normal, the machine is not slow — something specific on it is."
        ),
        keywords=("slow", "sluggish", "lag", "laggy", "freezing", "performance", "hang",
                  "cpu", "memory", "ram", "fan", "hot"),
    ),
    FaqEntry(
        question="The disk is full or Windows warns about low space",
        answer=(
            "Clearing temp files and the browser cache recovers space on most machines and "
            "both run automatically — neither touches documents, downloads or the recycle "
            "bin. If the disk is still full afterwards, it is real data rather than "
            "clutter, and someone has to decide what moves off."
        ),
        keywords=("disk", "space", "full", "storage", "drive", "cleanup", "temp", "cache",
                  "low", "free"),
    ),
    FaqEntry(
        question="The taskbar, Start menu or desktop is frozen",
        answer=(
            "Restarting Windows Explorer fixes almost all of these and ASTRA can do it "
            "automatically — it is far quicker than a reboot and open applications are not "
            "closed. Icons briefly disappearing while it restarts is normal."
        ),
        keywords=("taskbar", "start", "menu", "desktop", "explorer", "frozen", "icons",
                  "unresponsive", "click", "stuck"),
    ),
    FaqEntry(
        question="Chrome or Edge is slow, hanging, or will not open",
        answer=(
            "Restarting the browser clears most hangs and ASTRA can do it automatically; "
            "clearing the browser cache is the next step when pages load wrongly rather than "
            "not at all. If one specific site fails while everything else works, that is the "
            "site or DNS rather than the browser."
        ),
        keywords=("chrome", "edge", "browser", "firefox", "tab", "tabs", "website",
                  "page", "loading", "crash", "hanging"),
    ),
    FaqEntry(
        question="Zoom will not start or is stuck in a meeting",
        answer=(
            "Restart Zoom — ASTRA can do that automatically, and it clears the case where "
            "Zoom still thinks it is in a call that ended. If audio or video is missing "
            "afterwards, that is Windows microphone and camera permission, not Zoom."
        ),
        keywords=("zoom", "meeting", "webinar", "call", "stuck", "black", "audio", "video",
                  "microphone", "camera"),
    ),
    FaqEntry(
        question="Windows updates keep failing to install",
        answer=(
            "Check disk space first — updates fail to download on a full disk, and clearing "
            "temp files runs automatically. If space is fine and the same update keeps "
            "failing, resetting the Windows Update components is the fix, and that one is "
            "admin-only, so it waits for an admin to approve it."
        ),
        keywords=("update", "updates", "windows update", "failing", "failed", "error",
                  "install", "patch", "stuck", "reboot"),
    ),
    FaqEntry(
        question="Does ASTRA support Mac or Linux?",
        answer=(
            "Not today — the agent is Windows-only, and that is where the self-healing "
            "actions are defined. Mixed fleets are worth a conversation with the ASTRA team "
            "about what coverage you need."
        ),
        keywords=("mac", "macos", "apple", "linux", "ubuntu", "android", "ios", "mobile",
                  "server", "windows", "platform", "supported"),
    ),
)
