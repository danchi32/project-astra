# SAVIO Roadmap — Phases, Sub-phases and Modules

Status: **planned, nothing built yet.** Agreed in the planning discussion of 6–7 Nov 2026.
Work starts **Monday 9 Nov 2026** with Phase 1. Item codes (A1, L3, …) match the master
backlog; each module below says what it is, where it lands in the code, what it depends on,
and when it is done.

Read §0 once — it applies to every module and is what keeps a module from stalling halfway.

---

## 0. Rules for every module

### 0.1 Strategy filter
Build a feature only if it fills a gap the big vendors leave: price, complexity (no IT team),
India-specific needs (DPDP, Aadhaar/PAN, Hindi, cracked licences, ₹ billing), five tools →
one agent, live evidence instead of documents, AI you can verify, 20–200 PC companies.
Stay out of: antivirus/EDR, mobile MDM, full ITSM, 1000+ seat enterprise, macOS (for now).

### 0.2 Definition of Done (per module, per PR)
- [ ] Pydantic-validated, OpenAPI-documented endpoint(s); RBAC dependency on every route
- [ ] Audit-log entry for every mutation and every agent command
- [ ] Alembic migration for any schema change (next free revision: **0072**)
- [ ] Entitlement key checked on the route (see §7), not only hidden in the nav
- [ ] New remediation actions: registry entry in `backend/app/services/remediation/actions.py`
      **and** the agent's own switch (`SystemRemediationExecutor.cs` / Tray
      `RemediationExecutor.cs`) — the agent allowlist is independent by design
- [ ] Tests: pytest (backend), xUnit (agent), Vitest where portal logic is non-trivial
- [ ] `security-reviewer` run for anything touching agent commands, remediation tiers, auth,
      or data leaving a device (CLAUDE.md rule) — marked 🔒 below
- [ ] Docs updated (this file's status column, plus user-facing help where relevant)

### 0.3 Delivery mechanics
- **Branch → test locally → merge.** Every module is built on its own branch cut from the
  latest `main` (e.g. `phase1/f4-user-apps`, `phase1/a1-create-local-user`), tested locally
  first, and merged to `main` only once its tests pass. Nothing is built on `main` directly,
  and unrelated local changes (website, marketing) never ride along in a module branch.
- **Local test gate before opening the PR:**
  1. `docker compose -f infra/docker-compose.yml up -d`; backend `pytest` + `ruff check` green
  2. migrations: `alembic upgrade head` then `alembic downgrade -1` and back up, on a local DB
  3. portal `npm run build` (+ Vitest where added) for portal changes
  4. agent: `dotnet test`, then install the build on the test VMs and walk the module's
     "Done when" list by hand
- Then PR to `main`; CI = ruff + the full suite. The user merges PRs themselves, in the
  order of the sub-phase table, one at a time.
- **Shared-staging gotcha:** every PR's deploy check runs `alembic upgrade head` against the
  shared staging DB. Merge migration-carrying PRs promptly, in order, or other PRs fail with
  "Can't locate revision".
- Agent release ritual: bump `<Version>` in `agent/src/Directory.Build.props` (only place),
  commit, push annotated tag `agent-vX.Y.Z`; `agent-release.yml` signs the update manifest;
  then rebuild the portal installers for new installs.
- Agent versions: Phase 1 → **0.14.0**, Phase 2 → 0.15.0, Phase 3 → 0.16.0 (+ browser
  extension 1.0), Phase 4 → 0.17.0, Phase 5 → 0.18.0. Backend-only modules ship any time.
- Old agents must keep working: the backend refuses to queue an action a device's agent
  version can't run, and says so (don't let a task sit "pending" forever).

### 0.4 Known constraints found while planning
| Fact | Consequence |
|---|---|
| Installer is **unsigned** today (`ASTRA_SIGNTOOL` unset; build supports it) | Fine for pilots; paid rollout needs an OV code-signing cert (Azure Artifact/Trusted Signing does **not** accept India-registered orgs) |
| Update **manifest** signing is live (pinned key, CI-held private key) | Auto-update is safe to rely on for every phase |
| No cron / scheduler in the backend — derived data is computed on ingest by design | Anything time-based (briefs, 7-day recurrence checks) needs a decision — see 2.0 |
| No Tray ↔ Service local IPC exists | B2 needs a new, narrow named pipe — see 1d |
| No PDF library in backend | Reports are print-styled portal pages; "Download PDF" = browser print (stdlib before a dependency) |
| AI has only 5 tools | L3 widens them (Phase 1) |
| Notifications are emitted only for "approval needed", "remediation failed" and support requests; `TELEMETRY`/`ASSET` categories exist but nothing emits them; no forecasting anywhere | Decks' "warns before it happens" claim is not true today — N1 (Phase 1) and N2 (Phase 2) make it true; until then decks say "spots problems the moment they appear" |
| Hardware collector sends only manufacturer/model/name/RAM; `assets` already has `serial_number` + `warranty_expiry` (manual today) | Serial + BIOS come in Phase 1 (L5a); warranty lookup in Phase 2 (L5b); battery/disk health in Phase 2 (F1) |
| Compliance "defender"/"firewall" checks only test that the service is running | F1 replaces them with real state |
| Infra is in **Singapore**, not India | Say so in sales and the DPA; India residency is a later, demand-driven move |
| Legal docs are published but **not lawyer-reviewed** | Review before Phase 3 (DLP) goes to customers |

---

## Phase 1 — Foundation + Sales Engine

**Goal:** everyday IT chores in the portal, and a free Health Check that sells.
**Ships:** agent 0.14.0 + backend/portal. **Sellable after:** Free IT Health Check (lead
engine), Software & Provisioning add-on, "AnyDesk replacement" pitch (L4, marketing only).

| Sub-phase | Modules | Runs | Agent? |
|---|---|---|---|
| 1.0 Prep | decisions + test rig | first 1–2 days | — |
| 1a Agent data | F4, L2, L5a | first | yes |
| 1b Backend-only | E1, L3, N1 | parallel with 1a | no |
| 1c Actions | A1, A2 + A4 | after 1a | yes |
| 1d Offline | B1, B2 | parallel with 1c | yes |
| 1e Health Check | L1 | after 1a data exists | no |
| 1f Release | security review, QA, 0.14.0 | last | yes |
| 1z Compliance track | Z1–Z6 (our own DPDP readiness) | parallel, whole phase | no |

### 1.0 Prep (before code)
- **Founder decisions:** (1) winget catalog v1 — 20–30 package IDs; (2) wording of the Support
  Access consent text; (3) whether A1's "make administrator" option ships in v1.
- **Test rig:** Windows 11 VM (workgroup) + Windows 10 VM; one with a second local user;
  one without winget (LTSC or winget removed) to test the "not available" path.
- **Founder, in parallel (long lead time):** apply for the OV code-signing certificate;
  trademark search for "SAVIO".

### 1a — Agent data

**F4 · Per-user installed apps**
- Problem: `InstalledAppsCollector` reads only HKLM, so per-user installs (ChatGPT, Claude,
  Cursor, Ollama, Zoom per-user) are invisible.
- Agent: also enumerate `HKEY_USERS\<SID>\Software\Microsoft\Windows\CurrentVersion\Uninstall`
  for every **loaded** user hive (logged-in users). Do not load offline `NTUSER.DAT` files.
  Tag each row with scope `machine` | `user` and the SID's username.
- Backend: add `scope` + `user` columns to `DeviceInstalledApp` (migration); dedupe key
  includes scope; banned-software and compliance checks see both.
- Done when: a per-user app installed under user B appears while B is signed in, tagged
  `user`; machine-wide apps unchanged; existing tests green.

**L2 · Windows/Office activation + crack-tool check**
- Agent: new collector reading `SoftwareLicensingProduct` (WMI) for Windows (+ Office where it
  registers there): `LicenseStatus`, `PartialProductKey` present, `KeyManagementServiceMachine`.
  Flag KMS pointed at `localhost`/`127.0.0.1` or a non-corporate host. Office Click-to-Run
  licensing is best-effort; say "unknown" rather than guess.
- Crack tools: a **server-maintained** signature list (names of apps, services, scheduled
  tasks such as KMSpico/KMSAuto/AutoKMS) matched against data the agent already sends plus a
  scheduled-task name list. No file scanning in this phase.
- Backend: `device_licensing` table (one row per product per device); new compliance check
  `genuine_windows` and `no_activation_tools`.
- Done when: a genuine VM shows "Licensed"; a VM pointed at a fake KMS host is flagged;
  unknown states read "unknown", never "pass".

**L5a · Serial number + BIOS**
- Already there (found 9 Nov): the agent reads `Win32_BIOS.SerialNumber` at enrollment
  (`DeviceIdentity.cs`) and the backend stores it in `devices.serial_number`. So L5a is the
  remainder below, not a new collector.
- Agent: add `SMBIOSBIOSVersion` + release date and
  `Win32_ComputerSystemProduct` (`IdentifyingNumber`, `UUID`) to the hardware collector.
  Treat OEM placeholders ("To Be Filled By O.E.M.", "Default string", "System Serial
  Number", all zeros) as **no serial**, never as a real one.
- Backend: store on the device; when the device is linked to an asset and the asset's
  `serial_number` is empty, fill it (never overwrite a value an admin typed). Normalise the
  manufacturer string ("Dell Inc." → Dell, "HP"/"Hewlett-Packard" → HP, "LENOVO" → Lenovo)
  for L5b.
- Done when: VM/real-PC serials appear on the device page; placeholder serials show as
  "not available"; admin-entered asset serials are untouched.

### 1b — Backend-only (parallel)

**E1 · Support Access consent** 🔒
- Today `POST /platform/organizations/{id}/view-token` mints a read-only view-as token with
  no customer consent (audited under the org, but not consented).
- Add `support_access_until` (nullable timestamp) to the organization (migration).
- Portal Settings → "Allow SAVIO support to view your portal" with 1 h / 24 h / 72 h and
  "Revoke now"; each change audited.
- `create_view_as_token` refuses unless `support_access_until > now`; token lifetime is
  capped at the remaining window. Platform UI shows "Access not granted" with a
  "Request access" button that notifies the org's admins.
- Done when: no window → 403; window open → token works and expires at window end; grant,
  revoke and every view are in the customer's audit log.

**L3 · Ask SAVIO — widen the AI's evidence tools**
- `backend/app/services/ai/tools.py` today: `list_devices`, `get_device_telemetry`,
  `get_device_events`, `search_knowledge_base`, `propose_remediation`.
- Add read-only, org-scoped tools: `get_installed_apps`, `get_services`,
  `get_windows_updates`, `get_compliance` (device or fleet), `get_licensing` (needs L2),
  `find_assets` (warranty, assignee, purchase date), `fleet_summary` (counts by problem).
- **Tracker data stays out** unless the org has `workforce_insights` and the asking user's
  role may read it — employee monitoring never leaks through the chat.
- Tool outputs are data: keep them in the existing tool-result channel, never concatenated
  into the system prompt (prompt-injection hygiene; C3 hardens this further).
- Done when: "which PCs have Defender off?", "whose warranty ends this month?", "which apps
  are on fewer than 3 PCs?" answer correctly against seeded data (pytest with a fake model).

**N1 · Early-warning alerts (on ingest, no scheduler)**
- Today the portal shows problems only when someone opens it; nothing pushes, nothing
  predicts. N1 adds push alerts evaluated when telemetry arrives (fits the "computed on
  ingest" design — no cron).
- **Edge-triggered:** a small `alert_states` table (device, check key, state, since); a
  notification fires only on a change healthy → unhealthy (and a quiet "recovered" on the
  way back), never every minute.
- Checks: Defender real-time / firewall off (service-level until F1 lands), disk below the
  critical threshold, banned software appeared, burst of critical events, licensing turned
  non-genuine (L2).
- **The real early warning — disk-fill forecast:** from `TelemetryDailyRollup.disk_free_min_pct`
  over the last 14 days, a simple least-squares slope → "C: will be full in ~N days"; alert
  when N ≤ 7 (warning) / ≤ 2 (critical); suppressed when there are fewer than 5 days of data
  or the trend is flat/positive.
- Delivery: in-app (category `TELEMETRY`) for all; **email for critical** to org admins via
  the existing Resend integration, with an org setting to turn email off. Each alert links to
  the device and, where one exists, the fix action.
- Done when: forcing the VM's disk to fill over simulated daily rollups raises "full in ~N
  days" once (not repeatedly); stopping Defender raises one alert and one "recovered" on
  restart; a flat disk never alerts.

### 1c — Actions

**A1 · Create local user** 🔒
- Registry: `create_local_user`, tier **admin_only**, `execution_context="system"`,
  `operator_only=True`, params `username`, `full_name`, `make_admin`.
- Validation: reuse `_validate_username`; new `_validate_full_name` (length, printable);
  `make_admin` strict boolean.
- Agent: `LocalAccountManager.Create(...)` in the same API family as enable/disable; password
  generated on the device exactly like `LocalPasswordReset` (returned once, must-change at
  next sign-in); refuse on a domain controller; refuse if the name exists.
- Portal: device page → "Create local user" form; shows the one-time password once.
- Done when: user created on the VM, forced to change password, admin only when asked;
  duplicate name refused with a clear message; AI cannot propose it.

**A2 · Software catalog (winget)** 🔒
- Data: `software_catalog` (global, curated by us: winget ID, display name, publisher,
  silent-install support) + `org_catalog_items` (which entries an org enabled).
- Registry: `install_package`, tier **approval_required**, system context,
  `operator_only=True`, param `package_id` — accepted only if it is in the org's enabled
  catalog (server-side allowlist, like `SAFE_SERVICES`).
- Agent: resolve `winget.exe` for SYSTEM (DesktopAppInstaller path), run
  `winget install --id <id> --exact --scope machine --silent --accept-package-agreements
  --accept-source-agreements`; map exit codes to clear messages. Report winget availability
  in telemetry so the portal greys out devices that can't install.
- Done when: Chrome installs on the Win11 VM; the no-winget VM reports "winget not
  available" instead of failing silently; an ID outside the catalog is refused by the backend.

**A4 · Push to chosen devices + per-device status**
- New `deployments` table (who, action, params, target summary, created_at) and
  `deployment_id` on remediation tasks.
- Targeting: `device_ids` + `group_ids` + `exclude_device_ids`, resolved **at creation**
  (snapshot) and capped (existing bulk cap 1000).
- Status rollup: pending / running / succeeded / failed (with message) per device; offline
  devices run when they come back. **Check:** remediation task expiry — deployments need a
  window of at least 7 days.
- Portal: "Software" page → pick package → pick devices/groups/exclusions → confirm →
  live status table; reuse `/fleet/remediate` internals.
- Done when: push to a group minus one device creates exactly the right tasks; an offline
  VM installs after reconnecting; the deployment page reflects it.

### 1d — Offline

**B1 · Offline network self-heal**
- Agent: new `NetworkHealthWorker` in the Service. When the backend is unreachable, decide
  why: no IP / APIPA (169.254.x), gateway unreachable, DNS failing, or "only our backend is
  down" (do nothing in that case).
- Ladder: flush DNS → renew IP → restart adapter, re-testing after each step. Limits:
  at most 3 ladders/hour, adapter restart at most once/hour, never during an active
  remote-control session.
- Journal each step to `%ProgramData%\SAVIO\offline-journal.jsonl`; upload on reconnect
  via a new `POST /agent/offline-events` → audit log (actor = the device).
- Only automatic-tier network fixes run offline. Nothing approval_required or admin_only.
- Done when: disabling the adapter's DHCP lease on the VM gets fixed by the ladder; the
  journal appears in the audit log after reconnect; rate limits hold.

**B2 · Tray "Fix my internet"** 🔒
- New local named pipe on the Service: **one verb, no parameters** ("run network ladder").
  ACL: interactive users only; Service enforces the same cooldowns as B1; replies with a
  short status for the Tray to show.
- Tray: menu item + simple progress / result text (Hindi + English strings).
- Done when: works with the network cable out; repeated clicks respect the cooldown;
  security review confirms the pipe exposes nothing else.

### 1e — Free IT Health Check

**L1 · 7-day IT Health Check report**
- Backend: `GET /reports/health-check` aggregating what already exists — compliance results,
  disk/CPU/RAM rollups, pending updates, banned software, L2 licensing, asset age/warranty,
  plus "₹ at risk" lines only where we can show the arithmetic.
- Portal: `/reports/health-check` — a print-styled page (cover, score, top 10 findings,
  per-device appendix); "Download PDF" uses the browser's print. Shows "data collected for
  N of 7 days" until a week of data exists.
- Funnel: website CTA "Free IT Health Check" → register (existing trial) → install agent →
  day-7 email with the report link (existing Resend).
- Done when: a seeded org renders a credible report; every number traces to a query; the
  page prints cleanly in light theme.

### 1f — Release
- 🔒 `security-reviewer` on A1, A2, B2 and E1 together before the tag.
- QA pass on both VMs; release notes; bump to 0.14.0; tag `agent-v0.14.0`; rebuild installers.
- Update help centre: Software page, Create user, Fix my internet, Support Access.

### 1z — Compliance track (SAVIO's own DPDP readiness)

We sell DPDP Autopilot, so we have to be compliant first. Checked 9 Nov 2026: privacy
notice, DPA, sub-processor list, named grievance officer (48 h ack / 30 day resolve) and a
72-hour breach policy (6 h to CERT-In) are published. Roles: we are the **Data Processor** for
customers' employee/device data and the **Data Fiduciary** for our own accounts, billing,
website leads and marketing. Main DPDP obligations apply from ~13 May 2027.

| # | Module | Owner | Definition / done when |
|---|---|---|---|
| **Z1** | India log sink + retention | Claude (infra) | A Cloud Logging bucket in `asia-south1` with a log sink from the backend/Cloud Run/jobs, retention **≥ 365 days** (DPDP Rules: processing logs ≥ 1 year; CERT-In: 180 days within India). Verify the current `_Default` bucket retention. Closes the "open action" in `docs/legal/SECURITY_INCIDENT_POLICY.md` §7. Done when new logs land in the India bucket and the retention setting is captured in a deploy script, not set by hand |
| **Z2** | Per-person data export / erase | Claude (backend) | First **verify** what exists. Then an admin-only, audited action: "export everything about this person" (account, devices assigned, Tracker data, chats, audit entries about them) as a file, and "erase this person" with a dry-run count first. Erase never removes audit entries required for security/legal — they are pseudonymised instead, and the UI says so. Done when a seeded user's data exports completely and erases cleanly in a test |
| **Z3** | Record of Processing | Claude drafts, founder reviews | `docs/legal/RECORD_OF_PROCESSING.md`: each data category → purpose, lawful basis, role (fiduciary/processor), where stored, sub-processors, retention, who can access |
| **Z4** | Incident Deputy | Founder | Fill "[Name — assign]" in the incident policy |
| **Z5** | Sub-processor DPAs | Founder | Confirm the standard DPAs of Google Cloud, Neon, Anthropic, Vercel, Resend, Sentry, Razorpay/Paddle are accepted; keep copies |
| **Z6** | Lawyer review | Founder | Review Privacy Policy, DPA, Terms, EULA. **Ask explicitly:** does the 1-year retention of personal data/processing logs bind us as processor for customer telemetry, given raw telemetry is deleted after 7 days? Change retention only on that answer |

Also: list who at Technomate can reach the production database, and keep that access logged.

---

## Phase 2 — Trust + Security Score + AI IT Manager (core)

**Goal:** "the AI IT admin you can verify", a real security score, and a proactive AI.
**Ships:** agent 0.15.0 (F1 collector) + backend/portal.

| Sub-phase | Modules |
|---|---|
| 2.0 Decision | scheduling approach |
| 2a | F1 Security Score |
| 2b | C3 Hijack-proof AI |
| 2c | C1 Proof-of-Fix |
| 2d | C2 Canary rollout |
| 2e | J1 Brief, J2 Recommendations, J5 Value report |
| 2f | L5b Warranty lookup |
| 2g | N2 Scheduled alerts — device gone silent (no heartbeat for N hours), warranty expiring 90/60/30 days, agent rollout stuck; uses the 2.0 scheduler; same edge-triggered `alert_states` as N1 |

**2.0 Decision — how time-based work runs.** The backend has no scheduler on purpose. Options:
(a) Cloud Scheduler calling an authenticated internal endpoint per job; (b) compute lazily
when a page/email is requested and cache it. Recommendation: (a) for J1 emails and C1's 7-day
recheck, kept to a handful of idempotent jobs. Decide before 2c/2e.

**F1 · Security Score**
- Agent: BitLocker (`Win32_EncryptableVolume`), Defender real state (`MSFT_MpComputerStatus`:
  real-time protection, signature age), firewall per profile (`MSFT_NetFirewallProfile`),
  local Administrators members, TPM, Secure Boot; plus serial/BIOS, battery health, disk
  health for later (L5/F5). (Serial/BIOS already arrive from L5a.)
- Backend: replace the service-running checks with real state; weighted score per device and
  fleet; each failed check maps to a fix action where one exists.
- Done when: turning off real-time protection on the VM fails the check within one cycle.

**C3 · Hijack-proof AI** 🔒
- Mark every tool result that carries free text from outside (event messages, KB articles,
  user chat) as untrusted. A proposal whose justification relies on untrusted text is raised
  to `approval_required` regardless of the action's own tier.
- Red-team test suite: event-log and KB payloads that try to trigger actions; must all fail.
- "AI Safety" report: proposals made, raised, refused, and why.

**C1 · Proof-of-Fix**
- Capture an evidence snapshot before and after every remediation (the metric that
  triggered it); verify; schedule a 7-day recurrence check (per 2.0).
- Evidence card on the task page; feeds J5.

**C2 · Canary rollout** 🔒
- On top of A4 deployments: waves (1 device → 10% → rest), a health gate between waves
  (task success + no new critical events), auto-halt on failure.
- "Undo" only where an inverse action exists (block↔unblock USB, disable↔enable account);
  otherwise halt-only, and the UI says so.

**J1 / J2 / J5 · AI IT Manager core**
- J2 Recommendations: `recommendations` table (evidence, impact in ₹/risk/time, effort,
  linked action); generated from F1, L2, assets, telemetry; dismiss with reason.
- J1 Brief: daily (admin) and weekly (owner) summary email; business language; Hindi option.
- J5 Value report: hours saved (auto-fixed tasks × configured minutes), incidents prevented,
  ₹ saved — every number traceable.

**L5b · Warranty lookup**
- **Official manufacturer APIs only — no website scraping** (CAPTCHAs, terms of use, breaks
  when the site changes). One connector per vendor behind a small interface:
  Dell (TechDirect, OAuth2, up to 100 service tags per call), HP (developer-portal key,
  reportedly renewed every 90 days), Lenovo (client token); Microsoft Surface,
  Toshiba/Dynabook, Fujitsu after verifying their current access. No vendor publishes a
  price for these APIs; access is approval-gated and terms may limit lookups to devices the
  key holder owns or services. So support **both** a platform key (ours, as a secret) and a
  per-org "bring your own key" (HP access is reportedly approved per customer). Confirm each
  vendor's terms when applying, before relying on one shared key for every customer.
- No API (Acer, Asus, MSI, locally assembled PCs): **invoice upload → AI extracts** purchase
  date, vendor, warranty period, cost; plus CSV import.
- Asset gets `warranty_source` (dell_api | hp_api | lenovo_api | invoice_ai | manual | csv)
  and `warranty_checked_at` (migration). A lookup never silently overwrites a manual value —
  a mismatch is shown and the admin picks.
- When: on first sight of a serial, on a "Refresh warranty" button, and weekly (per 2.0).
- Feeds: expiry alerts at 90/60/30 days (J2), the Health Check (L1), the refresh planner (L5).
- Done when: a real Dell/HP/Lenovo serial resolves to the vendor's date; an invoice PDF fills
  an Acer asset; a manual date is never replaced without the admin choosing.

---

## Phase 3 — AI Smart Guard + DPDP

**Goal:** stop client-data leakage and be DPDP-ready before ~13 May 2027.
**Ships:** agent 0.16.0, browser extension 1.0 (Chrome/Edge/Brave; Firefox build), native
messaging host. Largest phase — split into 3a then 3b.

### 3.0 Spikes (before committing scope)
1. **Tenant restriction per service** (D2): which of Google, Microsoft, Dropbox, Slack,
   ChatGPT, Claude honour an "allowed tenant" request header set by an MV3 extension;
   fallback per service is block or strict DLP.
2. **Force-install on non-domain Windows:** `ExtensionInstallForcelist` with a Web-Store
   (unlisted) extension on Chrome and Edge; Firefox via `policies.json`.
3. **Classifier size/latency** on a 4 GB RAM PC for D4/D5.

**Founder before 3a starts:** Chrome Web Store, Edge Partner Center, Firefox AMO accounts;
lawyer review of docs + DLP/employee-monitoring opinion; employee notice template.

### 3a — AI Smart Guard (entitlement `ai_guard`, off by default, per-org)
- **D10 Anti-tamper + D1 Web control + D2 Corporate-account-only:** agent writes browser
  policies (Chrome/Edge registry, Firefox `policies.json`): force-install extension,
  incognito off, developer mode off, URL block/allow by category and group; unsupported
  browsers blocked or uninstalled per policy.
- **D3 Extension + native host** 🔒: MV3 extension intercepts paste, file input,
  drag-and-drop, form submit on watched sites; talks only to the local agent via native
  messaging (policy offline, device identity).
- **E4 Scanner isolation** 🔒: content analysis runs in a separate process with outbound
  network blocked by firewall rule; it talks to the agent over a fixed schema with **no
  free-text field** (category, counts, site, action, hashes of files only).
- **E3 Outbound Ledger:** readable local copy of everything the agent sends + portal page.
- **D4 Detectors:** Aadhaar (Verhoeff), PAN, GSTIN, card (Luhn), +91 mobile, email,
  IFSC+account; bulk/structured "contact list" detection; admin keywords.
- **D5 Zero-config discovery:** low-priority scheduled file scan → sensitivity map by folder
  (counts only) → suggested policies for the admin to approve.
- **D7 Coaching:** warn / justify / block dialogs in-page, Hindi + English.
- Actions available: log, warn, justify, redact (where supported), block. Default for a new
  org: **log-only for 14 days** (the pilot mode, E8).

### 3b — Compliance packs
- **I1 DPDP Autopilot:** data map (from D5), safeguards evidence (F1), retention
  suggestions, breach workflow (J7), readiness score with a task list. Obligations and
  timelines confirmed by the lawyer before any marketing claim.
- **I4 Client-Audit Pack:** upload questionnaire (xlsx/csv) → AI answers each row from L3
  evidence tools with citations; unanswerable rows marked as gaps with a fix link.
- **J3 Board report, J4 Compliance packs, J7 Incident report:** print-styled pages (same
  approach as L1).

---

## Phase 4 — Smart Guard advanced + lifecycle

| Module | Definition | Notes |
|---|---|---|
| **D6 Safe-AI mode** | Pseudonymise names/numbers before they reach ChatGPT/Gemini/Claude; restore in the reply | Per-site DOM integration is fragile — start with 3 sites, feature-flagged |
| **D8 Insider risk** | Per-user baseline from Guard events; HR "resigned" flag → watch mode; user risk score | Privacy review; ties to A6 |
| **D9 Admin AI investigations** | L3-style tools over Guard events ("what did X send?") | Role-gated like Tracker |
| **A3 Package upload** 🔒 | Admin uploads MSI (EXE later); stored in GCS; SHA-256 recorded; agent downloads via short-lived URL and verifies hash before running | Size cap; admin_only upload + deploy; security review mandatory |
| **A5 Onboarding bundle** | Ordered chain: A1 → A2/A3 installs, one approval | Needs A1, A2, A3 |
| **A6 Offboarding** | Disable account, sign out sessions, uninstall listed apps, mark asset "return pending", stop watch mode | Most actions exist already |

---

## Phase 5 — Platform hardening

| Module | Definition |
|---|---|
| **F2 Patch management** | Maintenance windows per group; Windows updates in window; third-party updates via `winget upgrade` for catalog apps |
| **F3 Policy baseline + drift** | Per-group profiles (screen-lock, guest off, USB, power); agent checks and reports drift; optional auto-reapply |
| **G1 Self-service App Store** | Employee requests a catalog app in the Tray → manager approves → A2 push |
| **G2 Mobile approvals** | PWA + web push first (no app-store dependency); native app only if needed |
| **J6 Smart alerts** | Dedupe/group, route by role, channels: email, WhatsApp, Teams, push |
| **E5 Update rings** | Per-org/group ring for agent updates; customer approves before wide rollout |
| **E6–E8** | VAPT + attestation, trust page/DPA/insurance, formal pilot programme (mostly non-code) |

---

## Later (decide with customer data)
C4 Fleet Immunity Network · C5 verified-fix pricing · D11 desktop channels/watermark ·
F5 hardware prediction · F6 lost device · G3 WhatsApp bot · G4 Hindi voice · G5 NL search ·
G6 weekly summary (covered by J1) · G7 printer/network/warranty · H1 MSP mode ·
H2 compliance reports · H3 savings reports · H4 scripts library · H5 macOS ·
I2 Ransomware Shield · I3 Licence Shield (mostly L2) · I5 Exit Shield (mostly D8 + A6).

**Not yet placed:** K1–K12 (Tally guard, CA asset register, AMC tracking, ISP uptime, Hindi
awareness, password-file scan, free email-security check, free exposure scan, auto IT docs,
certified wipe, insurance partnership, multi-branch), L5 hardware refresh planner (its data
arrives via L5a/L5b/F1), L6 owner WhatsApp report.

---

## 7. Entitlements (proposed — pricing discussion still open)

| Key | Covers | Default |
|---|---|---|
| existing `fleet_remediation` | A4 bulk push | Expert |
| new `software_provisioning` | A2, A3, A5, G1 | add-on |
| existing `lockdown` | A1, A6 | Professional |
| existing `ai_diagnose` | L3 | all plans |
| new `health_check` | L1 | all plans + trial |
| existing `compliance` | F1 score page | Expert; add-on below |
| new `ai_guard` | D-group, E3/E4 | per-org override only (like `workforce_insights`) |
| new `dpdp_autopilot` | I1 | add-on |
| new `audit_pack` | I4 | add-on |

Existing customers keep everything their plan grants today.

---

## 8. Founder checklist (no code)

| When | Task |
|---|---|
| Now | Z4 incident deputy · Z5 sub-processor DPAs · book the Z6 lawyer review · Change the decks' "notifies before issues happen" line to "spots problems across every PC the moment they appear" until N1 ships · OV code-signing certificate · "SAVIO" trademark search/filing · IP-assignment agreements · L4 "AnyDesk replacement" on website · apply for warranty API access: Dell TechDirect, HP developer portal, Lenovo (company name; approvals take time) |
| Phase 1 | winget catalog list · test VMs · consent text · 0.14.0 tag + installer rebuild |
| Phase 2 | 1–2 friendly customers for Proof-of-Fix and Canary |
| Before Phase 3 | lawyer review + DLP opinion · browser-store accounts · employee notice template · 2–3 pilot customers (CA firm, BPO) |
| Before first large customer | CERT-In empanelled VAPT · professional indemnity + cyber insurance |
| Phase 5 | antivirus whitelisting submissions · (native app accounts only if PWA is not enough) |
| Any time | DPIIT Startup India · Udyam MSME |

---

## 9. Status

| Phase | Status |
|---|---|
| 1 | Not started — starts 9 Nov 2026 |
| 2 | Not started |
| 3 | Not started (spikes first) |
| 4 | Not started |
| 5 | Not started |
