"""What the website assistant knows about the product, and where it comes from.

Two pieces, and the split matters.

`PRODUCT_BRIEF` is sent on **every** public question. It is the answer to "does the bot
know our product?" — features, the three plans and their prices, how a rollout works, what
the company does. A visitor asks things no FAQ list anticipates ("can it patch 200 laptops
overnight?", "how is this different from remote desktop?"), and a bot that had to match a
question against a list before it could say anything answered almost none of them. So the
whole product fits in the prompt, and retrieval only adds detail on top.

`PUBLIC_FAQ` is the detail: entries retrieved by word overlap when they are relevant. They
go deeper than the brief on one subject each.

Both are edited here, by hand, and every claim has to be one the website already makes.
A chatbot that invents a price or a certification does real damage, so when a fact changes
on the site it changes here in the same commit. Two files in particular travel with this
one: `website/src/components/PricingPlans.tsx` (and its runtime override,
`website/public/pricing.json`) for the numbers, and `website/src/app/astra/AstraContent.tsx`
for the feature list.

Retrieval lives in `faq.py`, which the portal's corpus shares.
"""
from app.services.ai.faq import FaqEntry

#: Everything the assistant is expected to know cold. Kept dense on purpose — it is
#: re-sent on every question, and it sits inside the cached prefix of the prompt, so its
#: cost is paid once per cache window rather than once per visitor.
PRODUCT_BRIEF = """# ASTRA, by Technomate IT Solution — product brief

## The company
Technomate IT Solution (technomateai.com) does three things: managed IT services
(proactive support, monitoring, patching, security, helpdesk — on-site and remote); supply
of business-grade hardware (laptops, desktops, workstations, servers, networking, sourced
and configured ready to deploy); and ASTRA, its AI operations product. Based in Ayodhya
Ganj, Dadri, Greater Noida, Uttar Pradesh 203207, India. Hours Mon-Sat, 10:00-19:00 IST.
Sales: sales@technomateai.com, +91 97115 31786. Product support: astra@technomateai.com.
The portal lives at astra.technomateai.com.

## What ASTRA is
An AI System Administrator for Windows fleets. A lightweight Windows agent (a service plus
a tray app) streams telemetry to the platform; an AI reasoning engine diagnoses problems
from that evidence and fixes them, either on its own or with IT approval. Employees can
also just describe a problem in plain language and let ASTRA investigate.

## How it works, end to end
Intent (understand the request) -> Knowledge (search the enterprise knowledge base) ->
Telemetry (collect live evidence from the device) -> Confidence (score the diagnosis) ->
Self-heal (act, within the allowed tier) -> Verify (confirm the fix and learn from it).
Evidence before action is the rule: it gathers before it acts, never the other way round.

## Capabilities
- Asset inventory: live, auto-discovered registry of every device, spec, app and licence.
- Live telemetry: CPU, RAM, disk, event logs, apps, services and Windows Update status,
  on a 60-second heartbeat, with an offline-safe queue.
- AI cognitive engine: an agentic reasoning loop over the telemetry and knowledge base.
- Self-healing: allowlisted, tiered remediations — automatic ones (restart Explorer,
  Outlook, Teams, Zoom; flush DNS; clear temp files; restart a network adapter), ones that
  need approval (Office repair, driver update, network reset), and admin-only ones
  (registry, firmware, reinstall-level work).
- Approval tiers: automatic / approval-required / admin-only, enforced in the backend
  code, never only in the AI's prompt.
- Patch management: push Windows Updates to one device or the whole fleet and watch the
  rollout live; every push is audited.
- Secure offboarding: disable a leaver's local account and force them out of their active
  Windows session in one click — matched by security ID, admin-only, fully audited.
- Conversational AI: employees describe the problem; ASTRA investigates and resolves.
- Compliance and security posture: a live dashboard scoring the fleet and flagging devices
  that fall short.
- Restricted-software detection: unapproved or risky applications surfaced across devices.
- Fleet correlation and mass remediation: the same fault linked across many devices and
  fixed for the whole affected group in one click.
- Helpdesk integration: connects to Freshservice and raises a ticket, with the device's
  evidence attached, for what it cannot fix — and only after the user agrees.
- Self-learning knowledge base: every confirmed fix teaches it; advice whose success rate
  falls is dropped.
- Asset assignment and acknowledgement: hand over a laptop and the employee is emailed to
  confirm receipt, from your own verified domain, with the signature kept on the record.
- Reporting, dashboards, proactive notifications, and a full audit trail.

## Plans and pricing (USD, per device)
- Essential — $4.49/device/month, or $44.90/device/year. Device inventory and asset
  tracking, live telemetry, patch management, AI assistant for diagnosis and guidance,
  reporting and dashboards, email support.
- Professional — $5.99/device/month, or $59.90/device/year. MOST POPULAR. Everything in
  Essential, plus the AI cognitive engine with automatic self-healing, approval tiers,
  secure offboarding and device lock-down, conversational AI resolution for employees,
  notifications and proactive alerts, priority support.
- Expert — $8.99/device/month, or $89.90/device/year. Everything in Professional, plus the
  compliance and security-posture dashboard, restricted-software detection, fleet
  cross-device correlation, one-click mass remediation, full audit trail and export,
  advanced RBAC (SSO in progress), a dedicated success manager.
Annual billing saves about 17%. Taxes may apply. Above 50 devices, sales quotes volume
pricing. A free trial is available and needs no credit card. Plans can change at any time;
billing adjusts on the next cycle from the active device count.

## Requirements and rollout
Windows devices and outbound HTTPS — nothing to host, the portal and API are managed. One
device is enrolled in minutes with an installer the portal generates; a fleet is deployed
through Intune, Group Policy or existing software distribution, and devices appear in the
portal as they check in. Windows only today: no macOS or Linux agent.

## Security
Least privilege throughout: role-based access control on every API, short-lived JWTs,
HTTPS only, encryption in transit and at rest, certificate-based agent enrolment, and an
audit log entry for every mutation and every command sent to a device. The agent executes
only allowlisted, approved actions.
"""


PUBLIC_FAQ: tuple[FaqEntry, ...] = (
    # -- what it is ------------------------------------------------------------
    FaqEntry(
        question="What is ASTRA?",
        answer=(
            "ASTRA is an AI System Administrator for Windows fleets, built by Technomate IT "
            "Solution. A lightweight Windows agent streams telemetry — CPU, RAM, disk, event "
            "logs, running apps, services and Windows Update status — back to the platform, "
            "and the AI engine reasons over that evidence to diagnose problems and fix them, "
            "either automatically or with IT approval."
        ),
        keywords=("astra", "product", "overview", "software", "platform"),
    ),
    FaqEntry(
        question="Who am I talking to?",
        answer=(
            "I'm the ASTRA assistant on Technomate's website — an AI that answers from the "
            "product documentation and FAQ. I can't see any account or device, and I can't "
            "make commitments on the company's behalf. For anything beyond what's documented, "
            "the team is one click away on the contact page."
        ),
        keywords=("who", "bot", "robot", "human", "real", "person", "assistant", "ai",
                  "chatbot", "hello", "hi", "hey"),
    ),
    FaqEntry(
        question="What can ASTRA actually do?",
        answer=(
            "Asset inventory, live telemetry on a 60-second heartbeat, an AI cognitive engine "
            "that diagnoses from evidence, tiered self-healing, Windows patch management "
            "across the fleet, secure offboarding, conversational AI for employees, "
            "compliance and security-posture scoring, restricted-software detection, "
            "fleet-wide correlation with one-click mass remediation, Freshservice helpdesk "
            "integration, a self-learning knowledge base, asset assignment with signed "
            "acknowledgement, reporting, notifications and a full audit trail."
        ),
        keywords=("feature", "features", "capabilities", "functionality", "offer",
                  "include", "modules"),
    ),
    FaqEntry(
        question="How does ASTRA fix problems on its own?",
        answer=(
            "Every remediation is allowlisted and falls into one of three tiers. Automatic "
            "fixes — restarting Explorer, Outlook, Teams or Zoom, flushing DNS, clearing temp "
            "files, restarting a network adapter — run on their own. Riskier ones, such as an "
            "Office repair or a driver update, wait for IT approval. Registry, firmware and "
            "reinstall-level actions are admin-only. The tiers are enforced in the backend, "
            "never only in the AI's prompt, and every command is audited."
        ),
        keywords=("self healing", "selfhealing", "remediation", "automate", "automatic",
                  "approval", "tiers", "guardrails", "risky", "safe", "control"),
    ),
    FaqEntry(
        question="How does the AI decide what to do?",
        answer=(
            "It follows the same loop every time: understand the intent, search the knowledge "
            "base, collect live telemetry from the device, score its confidence in the "
            "diagnosis, act within the tier it is allowed, then verify the result and learn "
            "from it. Evidence comes before action — it checks the machine rather than "
            "guessing from the words in a ticket."
        ),
        keywords=("work", "works", "engine", "reasoning", "decide", "diagnose",
                  "intelligence", "model", "confidence", "workflow"),
    ),
    # -- pricing ---------------------------------------------------------------
    FaqEntry(
        question="How much does ASTRA cost?",
        answer=(
            "Per device, per month, in three plans: Essential $4.49, Professional $5.99 and "
            "Expert $8.99. Annual billing is $44.90, $59.90 and $89.90 per device per year — "
            "about 17% off. Taxes may apply, and above 50 devices sales will quote volume "
            "pricing."
        ),
        keywords=("cost", "costs", "price", "pricing", "expensive", "cheap", "rate",
                  "seat", "licence", "license", "subscription", "billing", "quote",
                  "budget", "monthly", "annual", "yearly"),
    ),
    FaqEntry(
        question="What is in each plan?",
        answer=(
            "Essential ($4.49/device/month) covers device inventory and asset tracking, live "
            "telemetry, patch management, the AI assistant for diagnosis and guidance, "
            "reporting and dashboards, and email support. Professional ($5.99) adds the AI "
            "cognitive engine with automatic self-healing, approval tiers, secure offboarding, "
            "conversational AI for employees, proactive notifications and priority support. "
            "Expert ($8.99) adds the compliance dashboard, restricted-software detection, "
            "fleet correlation, one-click mass remediation, full audit export, advanced RBAC "
            "and a dedicated success manager."
        ),
        keywords=("plan", "plans", "tier", "tiers", "essential", "professional", "expert",
                  "difference", "compare", "includes", "package"),
    ),
    FaqEntry(
        question="Which plan should I choose?",
        answer=(
            "Most teams start on Professional — that is where the AI actually fixes issues on "
            "its own rather than only reporting them. Essential suits you if you mainly need "
            "visibility and patching; Expert is for compliance or audit requirements and for "
            "fleets big enough that fixing one fault across many machines at once matters."
        ),
        keywords=("recommend", "suitable", "choose", "pick"),
    ),
    FaqEntry(
        question="Can I change or cancel my plan later?",
        answer=(
            "Yes — upgrade or downgrade at any time. Billing adjusts on your next cycle based "
            "on the devices actually active, so you are never paying for machines you have "
            "retired."
        ),
        keywords=("change", "cancel", "upgrade", "downgrade", "switch", "contract", "lock",
                  "commitment", "refund", "term"),
    ),
    FaqEntry(
        question="Is there a free trial?",
        answer=(
            "Yes, and no credit card is needed to explore the platform. Sign up at "
            "astra.technomateai.com and enrol your first device with the installer the portal "
            "generates for you — it takes a few minutes."
        ),
        keywords=("trial", "free", "try", "evaluate", "poc", "pilot", "card", "demo",
                  "test", "signup", "sign up", "register", "buy", "purchase", "onboard",
                  "subscribe", "order"),
    ),
    FaqEntry(
        question="Do you offer volume pricing for a large fleet?",
        answer=(
            "Yes. Above 50 devices, contact sales for volume pricing and a guided rollout — "
            "sales@technomateai.com or +91 97115 31786."
        ),
        keywords=("volume", "discount", "bulk", "enterprise", "large", "fleet", "many",
                  "hundred", "thousand", "negotiate", "deal"),
    ),
    # -- getting started -------------------------------------------------------
    FaqEntry(
        question="What do I need to run ASTRA?",
        answer=(
            "Windows devices and outbound HTTPS. The agent installs as a Windows service plus "
            "a tray app, enrols with a token the portal issues, and starts reporting within a "
            "minute. There is nothing to host — the portal and API are managed for you."
        ),
        keywords=("requirements", "prerequisites", "server", "host", "hosting", "cloud",
                  "premise", "onprem", "infrastructure", "setup", "install"),
    ),
    FaqEntry(
        question="Does ASTRA work on Mac or Linux?",
        answer=(
            "Not today — the agent is Windows-only, and that is where the self-healing "
            "actions are defined. If you have a mixed fleet, talk to the team about what "
            "coverage you need; Technomate's managed IT services extend beyond Windows even "
            "where the ASTRA agent does not."
        ),
        keywords=("mac", "macos", "apple", "linux", "ubuntu", "android", "ios", "mobile",
                  "phone", "support", "platform", "os", "windows"),
    ),
    FaqEntry(
        question="How long does a rollout take?",
        answer=(
            "A single device is enrolled in minutes with the generated installer. For a fleet, "
            "the same installer is deployed through Intune, Group Policy or your existing "
            "software distribution, and devices appear in the portal as they check in."
        ),
        keywords=("rollout", "deployment", "deploy", "intune", "gpo", "group policy",
                  "onboarding", "mass", "distribute"),
    ),
    FaqEntry(
        question="Will the agent slow down employees' machines?",
        answer=(
            "It is deliberately lightweight: a background service that reports on a "
            "60-second heartbeat and queues its data when a machine is offline. Employees see "
            "a tray app they can chat to when something breaks, and nothing else."
        ),
        keywords=("performance", "slow", "heavy", "resource", "cpu", "impact", "intrusive",
                  "background", "battery", "overhead"),
    ),
    # -- individual capabilities ----------------------------------------------
    FaqEntry(
        question="Can ASTRA install Windows updates?",
        answer=(
            "Yes. Push Windows Updates to one device or the whole fleet from the admin panel "
            "and watch the rollout live, device by device. Every push is captured in the audit "
            "log. It is driven from Telemetry -> Updates in the portal."
        ),
        keywords=("patch", "patching", "update", "updates", "windows update", "wsus",
                  "vulnerability", "security patch", "rollout"),
    ),
    FaqEntry(
        question="What happens when an employee leaves?",
        answer=(
            "Secure offboarding disables the leaver's local account and forces them out of "
            "their active Windows session in one click — not just at next login. The right "
            "account is matched by its security ID rather than by name, it is an admin-only "
            "action, and every lock-down is audited."
        ),
        keywords=("offboarding", "leaver", "resign", "termination", "fired", "exit",
                  "disable", "lock", "employee", "departure", "data", "theft"),
    ),
    FaqEntry(
        question="Can employees ask ASTRA for help themselves?",
        answer=(
            "Yes — that is the point of the tray assistant. Someone describes the problem in "
            "plain language ('Outlook keeps freezing'), ASTRA checks the machine's telemetry "
            "and event log, and either fixes it or explains what it found. Fixes above the "
            "automatic tier are queued for the IT team instead of being applied silently."
        ),
        keywords=("employee", "user", "end user", "staff", "chat", "helpdesk",
                  "self service", "ticket", "conversational", "tray", "ask"),
    ),
    FaqEntry(
        question="Does ASTRA integrate with our helpdesk?",
        answer=(
            "Freshservice is supported: ASTRA raises a ticket for what it cannot fix itself, "
            "with the device's evidence attached, and only after the user agrees to it."
        ),
        keywords=("integration", "integrate", "freshservice", "jira", "servicenow",
                  "zendesk", "ticketing", "api", "connect", "webhook"),
    ),
    FaqEntry(
        question="How does ASTRA handle compliance and reporting?",
        answer=(
            "The Expert plan adds a live compliance and security-posture dashboard that scores "
            "the fleet and flags devices that fall short, plus restricted-software detection "
            "for unapproved applications. Every plan has reporting and dashboards for fleet "
            "health and resolution, and Expert adds full audit-trail export."
        ),
        keywords=("compliance", "audit", "report", "reporting", "posture", "policy", "iso",
                  "governance", "evidence", "export", "shadow it", "restricted"),
    ),
    FaqEntry(
        question="Does it get better over time?",
        answer=(
            "Yes — every confirmed fix teaches the knowledge base. ASTRA publishes what "
            "repeatedly works, drops advice whose success rate falls, and keeps the words "
            "users actually type, so retrieval matches how your staff describe problems "
            "rather than how a technician would write them up."
        ),
        keywords=("learn", "learning", "improve", "training", "knowledge base", "kb",
                  "smarter", "over time", "custom"),
    ),
    FaqEntry(
        question="Can I track which laptop is with which employee?",
        answer=(
            "Yes. Asset assignment records the handover, and the employee is emailed to "
            "confirm receipt — sent from your own verified domain, with the signed "
            "acknowledgement kept on the asset record."
        ),
        keywords=("asset", "assignment", "inventory", "track", "allocation", "laptop",
                  "acknowledgement", "handover", "custody"),
    ),
    # -- trust -----------------------------------------------------------------
    FaqEntry(
        question="Is my data secure?",
        answer=(
            "The platform is built on least privilege: role-based access control on every API, "
            "short-lived tokens, HTTPS everywhere, encryption in transit and at rest, "
            "certificate-based enrolment for every agent, and an audit log entry for every "
            "change and every command sent to a device. The agent only ever executes "
            "allowlisted, approved actions."
        ),
        keywords=("security", "secure", "privacy", "gdpr", "data", "encryption", "safe",
                  "trust", "breach", "protection", "rbac", "access"),
    ),
    FaqEntry(
        question="What data does the agent collect?",
        answer=(
            "Operational telemetry: CPU, RAM and disk usage, Windows event-log errors, "
            "installed and running applications, services, and Windows Update status — the "
            "evidence needed to diagnose a fault. It is an IT operations tool, not employee "
            "monitoring: no keystrokes, no screen recording, no browsing history."
        ),
        keywords=("data", "collect", "collected", "privacy", "monitor", "monitoring",
                  "monitored", "surveillance", "keylogger", "screen", "spy", "spying",
                  "telemetry", "gdpr", "personal", "employee", "employees", "staff",
                  "worker", "track", "tracking"),
    ),
    FaqEntry(
        question="Can the AI do something we didn't approve?",
        answer=(
            "No. It can only run actions from an allowlist, and each action carries a tier — "
            "automatic, approval-required, or admin-only. The tier is enforced in the backend "
            "code, so a persuasive message cannot talk the AI into a higher-privilege action, "
            "and every command is recorded in the audit log."
        ),
        keywords=("risk", "dangerous", "wrong", "mistake", "control", "oversight", "trust",
                  "hallucinate", "safety", "permission", "override", "rogue"),
    ),
    # -- company and contact ---------------------------------------------------
    FaqEntry(
        question="What else does Technomate do besides ASTRA?",
        answer=(
            "Managed IT services — proactive support, monitoring, patching, security and "
            "helpdesk, on-site and remote — and hardware supply: business-grade laptops, "
            "desktops, workstations, servers and networking, sourced, configured and "
            "delivered ready to deploy. Devices can be bundled with ASTRA for a fully managed "
            "rollout."
        ),
        keywords=("services", "managed", "hardware", "laptop", "laptops", "buy", "sell",
                  "sells", "purchase", "order", "supply", "supplier", "procurement", "amc",
                  "support contract", "company", "reseller"),
    ),
    FaqEntry(
        question="How do I book a demo or reach the team?",
        answer=(
            "Use the Book a demo button at the top of any page, or the contact form on the "
            "Contact page. You can also email sales@technomateai.com or call "
            "+91 97115 31786 (Mon-Sat, 10:00 AM - 7:00 PM IST)."
        ),
        keywords=("demo", "sales", "contact", "call", "email", "phone", "meeting", "talk",
                  "speak", "reach", "human", "someone", "book", "schedule"),
    ),
    FaqEntry(
        question="Where is Technomate based?",
        answer=(
            "Ayodhya Ganj, Dadri, Greater Noida, Uttar Pradesh 203207, India. Office hours "
            "are Mon-Sat, 10:00 AM - 7:00 PM IST."
        ),
        keywords=("address", "location", "office", "india", "noida", "delhi", "where",
                  "based", "hours", "timing", "visit"),
    ),
    FaqEntry(
        question="I already use ASTRA and need help with my account",
        answer=(
            "Sign in at astra.technomateai.com — Help & support there has the full guides, an "
            "in-portal assistant, and a form that raises a request with our team. You can also "
            "email astra@technomateai.com."
        ),
        keywords=("login", "sign in", "portal", "customer", "existing", "account",
                  "password", "ticket", "support", "help", "issue", "problem"),
    ),
)
