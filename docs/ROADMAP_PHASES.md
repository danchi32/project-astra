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
- **One branch per phase; `main` only when the whole phase is verified** (decided 9 Nov).
  Phase 1 lives on `phase-1` (cut from `main`). Each module is committed there and, once its
  local test gate passes, gets an annotated tag `phase1-<module>` (e.g. `phase1-f4`). Nothing
  reaches `main` until every Phase 1 module is done and verified end to end; then one PR
  `phase-1` → `main`. Unrelated local changes (website, marketing) never ride along.
- **Never tag `agent-v*` before the phase merges.** That tag triggers the signed release and
  every enrolled agent auto-updates. Test agent builds by installing them by hand on the
  test VMs.
- **Pushing a non-`main` branch deploys it to shared staging** (`deploy-staging.yml`) and
  runs its migrations there. The workflow skips migrations when staging is already ahead,
  so other branches don't break, but staging then runs this branch's code until someone else
  pushes. Push `phase-1` only when that is wanted.
- **Migrations inside a phase are numbered in order** (0072, 0073, …). If `main` gains a
  migration meanwhile, renumber ours before the phase PR.
- **Local test gate before opening the PR:**
  1. `docker compose -f infra/docker-compose.yml up -d`; backend `pytest` + `ruff check` green
  2. migrations: `alembic upgrade head` then `alembic downgrade -1` and back up, on a local DB
  3. portal `npm run build` (+ Vitest where added) for portal changes
  4. agent: `dotnet test`, then install the build on the test VMs and walk the module's
     "Done when" list by hand
- At phase end: full gate again on the whole branch, then the phase PR to `main`; the user
  merges it themselves. Only then tag `agent-v0.14.0` and rebuild installers.
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
- As built (9 Nov): two checks, `genuine_windows` ("Windows activated") and
  `no_activation_tools` ("No cracked activation"). **Office is not judged for activation** —
  a properly licensed Microsoft 365 laptop still shows `Office16O365…R_Grace` products in
  SPP notification mode (found on a real machine); Office is used only for the KMS-host
  check. Activators are matched in app *and* service names, so pre-0.14 agents are covered
  for that half. Scheduled-task names were left out of v1 (the service + app lists cover
  KMSpico/KMSAuto); add them only if a real miss shows up.

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
- As built (9 Nov): serial, BIOS version and BIOS date ride on the hourly hardware info, so
  serials read wrong (or never) at enrollment get corrected. One rule set in
  `app/services/hardware.py` cleans the serial at enrollment and on every push, and also
  clears placeholder **manufacturer/model** — assembled PCs report "To Be Filled By O.E.M."
  there too, and it must not reach the asset register. Linked assets get only their empty
  fields filled, with a history note. `normalize_vendor()` is ready for L5b.
  `Win32_ComputerSystemProduct` (UUID) was left out — nothing needs it yet.

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
- As built (10 Nov): `app/services/ai/fleet_tools.py`. Device tools (`get_installed_apps`,
  `get_windows_updates`, `get_device_compliance` — licensing is inside compliance) answer in
  the tray only for the caller's own PC. Fleet tools (`fleet_summary`, `find_assets`) are
  advertised only to portal admins/technicians and refused for anyone else. Also tightened
  an existing gap: `list_devices` in the tray used to return every hostname in the org; now
  only the caller's own. **Tracker data was left out entirely** — no chat tool reads it.
  Not verified against a live model locally (no API key in the dev env); the engine wiring
  and every tool are covered by tests with a recording fake.

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
- As built (10 Nov): `app/services/alerts.py` + `alert_states` (migration 0076). Checks run
  only when the push carries their data, so an inventory-less push can't "resolve" an
  inventory alert. Disk alert has hysteresis (on below 10 %, off only above 12 %). Forecast
  is least squares over ≤14 daily rollups, needs ≥5 points, ignores slopes under
  0.05 %/day, and compares the ROUNDED day count ("about 7 days" warns — found a float
  7.000000000001 miss in testing). Alerting runs in a savepoint after the ingest work and
  can never lose telemetry; critical emails go out after the commit, best-effort.
  Settings → Organization → Alerts toggles the email (default on).

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
- As built (11 Nov), extended on the user's request with a device **Users** tab: the agent
  reports local accounts hourly (`device_local_accounts`, migration 0077) and a new
  `set_local_admin` action (admin-only, elevated, withheld from AI) makes an account an
  administrator or a standard user — refusing built-ins and the change that would leave no
  enabled admin. Enable/disable reuse the existing actions. **Fixed in passing:** disabling an
  account that wasn't signed in used to sign out whoever WAS (the single-session fallback);
  with any account now disable-able from the tab that would log out the person at the desk,
  so only the target's own sessions (matched by SID) are ever signed out.
  Live-tested on a real Windows 11 laptop (elevated): create, duplicate refused, admin ⇄
  standard, disable ⇄ enable, built-in refused, list — then the test account was deleted.

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
- As built (11 Nov): catalog is a server-side constant (`app/services/software_catalog.py`,
  19 apps; WhatsApp left out — Store-only, per-user). Editing it from the portal is later.
  Live test as SYSTEM on a real laptop: winget found in WindowsApps, run as SYSTEM, catalog
  lookup works ("couldn't find" for an unknown id) — but the 7-Zip download (GitHub
  releases) timed out, from the user's own session too: that network blocks GitHub
  downloads. Error 0x80072EE2 now reads as a blocked download. Then a full install as
  SYSTEM through the agent's own code: Google Chrome 157.0.8103.50 -> 157.0.8103.51 in 283 s,
  "Installed Google.Chrome." (Chrome was already there, so winget upgraded it in place.)

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
- As built (11 Nov, B1+B2): `Net/NetworkDoctor.cs` (pure diagnosis + ladder + limiter, one
  shared instance), `NetworkHealthWorker` (2-min boot grace, then every 60 s) and
  `NetworkFixPipeServer` (`SAVIO.FixMyInternet`, one verb, INTERACTIVE may talk, NETWORK
  denied). New diagnosis the plan didn't have: **"internet works, only SAVIO is down"** —
  the ladder does nothing then, instead of restarting a healthy adapter. Journal at
  `%ProgramData%\SAVIO\offline-journal.jsonl`, uploaded to `/agent/offline-events` → audit
  log `device.offline_self_heal`. Live-checked on a real laptop: real probes and the real
  Tray↔service pipe (diagnosis "only SAVIO's server isn't answering"). The ladder's steps
  then ran live too, as SYSTEM on the same laptop (user's request): flush DNS ok, renew IP
  ok, restart Wi-Fi adapter ok (~48 s), back online after each. Remote-control-session guard
  not added yet.

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
- As built (11 Nov): `app/services/health_check.py` + `GET /reports/health-check` (admin and
  technician; outside the AUDIT_EXPORT-gated reports router, so every plan and the trial get
  it). Sections: score and counts, findings worst-first with machines named and an
  owner-facing "what to do", disks the N1 forecast says fill within a week, PCs over 4 years
  (purchase date, else BIOS date), warranty ending in 90 days, software (distinct apps,
  per-user installs, desktop AI tools by word match). Portal `/reports/health-check`, linked
  from Reports — including when Reports itself is behind an upgrade; "Download PDF" is
  `window.print()`, and the portal chrome is `print:hidden`. **No "₹ at risk" lines** — none
  could show its arithmetic from data we hold, so the report is counts only. Checked on
  Postgres with a seeded 4-PC fleet, on screen and with the print rules applied. Not done:
  the day-7 email (needs the Phase 2.0 scheduler decision) and the website CTA.

### 1f — Release
- 🔒 `security-reviewer` on A1, A2, B2, E1 and Z2 (erase deletes data) together before the tag.
  - Done 11 Nov (three parallel reviews). 7 High + 7 Medium found, every High re-checked in
    code, all fixed the same day:
    - **H1, older than Phase 1:** `ProgramData\Astra\agent.credential` was Users-readable, and
      it's LocalMachine DPAPI, so any local user could take the device token. Folder and file
      are now SYSTEM + Administrators only, re-applied on every load, which repairs existing
      installs.
    - **H2:** offline journal moved out of ProgramData to `...\Astra\state`, with a hardened
      ACL and junctions refused.
    - **H3:** the reachability probe now goes over HTTP through the agent's proxy.
    - **H4:** one-time passwords are shown only to an org admin, only for 24 h; never to
      technicians, view-as, the platform console or an export.
    - **H5:** AI telemetry and event tools are limited to the person's own PC without fleet
      access.
    - **H6:** view-as can't read the enrollment key or personal-data exports.
    - **H7:** erase and delete match audit entries by id, email and confirmed usernames,
      never a self-chosen full name.
    - **Medium:**
      - Tray checks the pipe is owned by SYSTEM (identification-level client, FirstPipeInstance).
      - winget gets a private TEMP.
      - The agent pins the catalog (`test_agent_catalog_matches`).
      - AnyDesk removed from the catalog.
      - Platform console lists follow the support window and are audited.
      - Export drops task results and params.
      - Operators can't delete their own org.
    - **Lows also fixed:**
      - deployment audit id
      - audited params
      - `create_task` refuses `operator_only` from the AI (admin_only proposals still wait for approval)
      - `package_id` type check
      - offline-event fixed values
      - chunked journal upload, capped journal
      - manual-run hourly cap
      - 2 s pipe read timeout
      - winget version sort and ARM64
      - operators can't be deleted by an org admin
  - Left open (low):
    - Network ladder doesn't pause during a remote session.
    - Circuit-breaker count/insert race.
    - Windows usernames in the export query string reach access logs.
    - `support-access-request` is unthrottled.
    - Tray `get_installed_apps` shows other profiles' apps on shared PCs.
    - Org delete doesn't clean the relay group or billing customer.
    - Self-approval for approval-tier pushes kept by design.
  - Live-checked 11 Nov on a real laptop. Hardening and the pipe server ran as SYSTEM
    (scheduled task); the Tray side ran as the de-elevated user (`runas /trustlevel`).
    - **Planted folder:** a user-owned folder with a Users-readable credential became owner
      Administrators, ACL SYSTEM + Administrators only.
    - **Junction:** refused.
    - **State folder:** created SYSTEM/Admin-only, and the journal was written into it.
    - **Reachability:** the HTTP probe through the proxy handler returned true.
    - **Pipe:** the Tray accepted the SYSTEM-owned pipe and got the real reply.
    - **Impostor pipe:** a user-owned pipe was refused ("Something other than SAVIO
      answered"), and its fake message was never shown.
    - **Read check:** the de-elevated user was denied reading the locked file.
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

- Z1 as built (11 Nov): before, every log was in `_Default` (location `global`, **30 days**);
  only Google's admin-activity audit logs (`_Required`) were kept 400 days. Now
  `infra/logging/india-log-sink.sh` keeps bucket `india-logs` in asia-south1 at 400 days and
  a sink copying every entry (`severity>=DEFAULT`) into it; `_Default` untouched. Applied to
  `astra-prod-503923`, re-run idempotently, entries confirmed landing in the bucket.
  `test_india_log_sink.py` pins region, retention floor and the catch-all filter. Not
  locked — waits for Z6. Neon and relay logs are outside this bucket (noted in the incident
  policy §7).
- Z2 as built (11 Nov): what existed was only `DELETE /users/{id}` (hard delete, cascades
  chats, writes the email into the audit log) — no export, no pseudonymisation. Added
  `app/services/personal_data.py` and, admin only, `GET /users/{id}/personal-data` (dry-run
  counts + suggested Windows usernames), `…/export` (JSON file, audited) and `POST …/erase`
  (typed-email confirm; not yourself, not a platform operator). A person = the portal user
  **plus the Windows usernames the admin ticks** — Tracker is keyed by `DOMAIN\user` and
  nothing links that to a portal user. Erase deletes account, chats, tokens, team
  memberships, escalations, Tracker/session/profile-app rows; unlinks assets, asset history,
  support tickets, deployments; pseudonymises audit entries (email, name, usernames →
  `erased-user-<hash>`, whole-token only); remediations / remote sessions keep the bare user
  ID. Device-side Windows accounts are listed, not touched (remove them with A1). Portal:
  Users → lock icon → "Personal data". Checked on Postgres through the UI with near-miss
  usernames (`ashadeep`, `ganasha`) surviving. Caught on the way: Postgres `LIKE` treats `\`
  as an escape, and the JSON text of an audit entry escapes it again — both handled and
  tested. Old hard delete left as is; Z2 erase is the DPDP path.
- Z3 as built (11 Nov, draft): `docs/legal/RECORD_OF_PROCESSING.md`, written from the code and
  production settings (secret names only), not from the published policies. Eleven
  activities, where data lives, Technomate staff access, a founder checklist, and **ten gaps
  (G1–G10)**. Biggest: the privacy policy doesn't describe Tracker and says the agent doesn't
  monitor browsing (G1); deleting an organisation leaves nine tables behind (G3); the
  sub-processor page misses n8n, Zoho Bigin and Telegram (G7). Founder review pending; no
  gap fixed in this module.
  Then fixed the three code gaps (11 Nov): G3 org deletion now removes the nine
  non-cascading tables (guard test for future tables), G6 AI answer cache expires after 90
  days, G10 plain user delete pseudonymises like Z2. G1, G2, G4, G5, G7, G8 and G9 stay with
  the founder / lawyer.

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

**N2 as built (16 Nov, on demand per the 2.0 decision):** `app/services/watchlist.py`,
`GET /watchlist` (staff), portal Operations → Watchlist. The same four lists the scheduled
alerts will use, shown when someone looks:
- **PCs gone quiet:** silent for over N hours (default 6, up to 30 days), counted from last
  seen, or from enrolment if never seen.
- **Warranties:** ending within 90 days or ended in the last 30, bucketed ended / 30 / 60 /
  90 days.
- **Stuck work:** queued over a day and never collected (likely off), or collected and never
  finished, named with its rollout.
- **Agents behind:** PCs older than the current signed release, compared only when an update
  channel is configured.

`test_watchlist.py`, 2 tests, covering each list, another org's PCs, the threshold, and
403. Checked on screen.

**Not built:** e-mails and notifications for new entries. When a scheduler exists, it calls
`watchlist.build` and fires on new entries through the N1 `AlertState` table, edge-triggered,
so an entry fires once and not every run.

**2.0 Decision — how time-based work runs.** The backend has no scheduler on purpose. Options:
(a) Cloud Scheduler calling an authenticated internal endpoint per job; (b) compute lazily
when a page/email is requested and cache it. Recommendation: (a) for J1 emails and C1's 7-day
recheck, kept to a handful of idempotent jobs. Decide before 2c/2e.
- **Decided (16 Nov): manual for now, scheduler when a client asks for it.**
  - Nothing runs on a clock yet. Reports are generated when someone asks for them.
  - J1 is built as an on-demand brief: view it, or e-mail it now with a button. It can be
    put on a schedule later without rewriting it.
  - N2's time-based alerts (a PC gone silent, warranty at 90/60/30 days, a stuck rollout)
    wait for the scheduler. An on-demand view of the same list can come earlier.
  - C1, C2 and J2 never needed a scheduler: they ride on agent pushes, or are computed when
    read.
  - When a client needs e-mails on a clock, option (a) is the plan: Cloud Scheduler calling
    one authenticated internal endpoint, with idempotent jobs recorded in a `job_runs`
    table.

**F1 · Security Score**
- Agent: BitLocker (`Win32_EncryptableVolume`), Defender real state (`MSFT_MpComputerStatus`:
  real-time protection, signature age), firewall per profile (`MSFT_NetFirewallProfile`),
  local Administrators members, TPM, Secure Boot; plus serial/BIOS, battery health, disk
  health for later (L5/F5). (Serial/BIOS already arrive from L5a.)
- Backend: replace the service-running checks with real state; weighted score per device and
  fleet; each failed check maps to a fix action where one exists.
- Done when: turning off real-time protection on the VM fails the check within one cycle.
- As built, backend slice (15 Nov, branch `phase-2`, not pushed): migration `0079`
  `device_postures` (one row per device, replaced on each report). Ingest takes an optional
  `posture` block: Defender real-time and signature age, the three firewall profiles,
  BitLocker on the OS drive. Each field may be null, and null means "not read", never "off".
  Checks: Defender fails when real-time is off or signatures are older than 7 days; Firewall
  names the profile that is off; BitLocker is a new check. A device with no posture row keeps
  the service-based Defender and Firewall checks, so an agent that has not updated scores
  exactly as before. `security_score` is weighted by check (`compliance.WEIGHTS`), per device
  and as a fleet mean; the old `score` is unchanged. Tests: `test_security_posture.py` (8).
  Migration checked up / down / up on Postgres 16.
  Agent side (15 Nov, not version-bumped; the bump happens at release): `PostureCollector`
  reads Defender (`root\Microsoft\Windows\Defender`), the firewall profiles
  (`root\StandardCimv2`) and BitLocker on the system drive (`root\CIMV2\Security\
  MicrosoftVolumeEncryption`). Every read is independent, and a null is "unknown". It runs
  on every push, so a Defender change reaches the backend within one cycle. The drive letter
  is validated before it goes into the WQL. Checked: 331 agent tests pass; Defender values
  match raw WMI on a real laptop; the firewall reads OFF on all three profiles, which
  `netsh advfirewall` confirms. BitLocker checked as SYSTEM (the way the agent runs): the
  collector reads it as off, and raw `Win32_EncryptableVolume` agrees on C: and D:
  (ProtectionStatus 0, ConversionStatus 0). **Still to do for 2a:** the portal display, and
  the live check that a Defender change reaches the backend within one cycle, which needs
  the agent 0.15.0 built and running on a VM. The 2a tag waits for both.
  - Portal (15 Nov): the compliance page shows a Security score ring beside Compliance, and
    the "Needs attention" table has a Security column. Checked on screen against a seeded
    Postgres fleet (one healthy PC, one with Defender, firewall and BitLocker off): fleet
    Security 68%, the bad PC 36%, and its failing checks listed.
  - Bug found on that check: migration 0079 had an `updated_at` column the model does not
    have, so the first real insert failed on Postgres. Tests run on SQLite from the models, so
    they missed it, and my earlier "up / down / up" check did not insert a row. Fixed, and a
    column comparison against the live table (Alembic `compare_metadata`) now shows no
    difference. Lesson for later modules: any migration check must also insert a row.
  - Agent 0.15.0 built (15 Nov): version bumped on `phase-2` (commit `1adb7c2`), not
    tagged. The build is in the scratchpad, outside the repo. 331 agent tests pass.
    - **Live install (16 Nov), on the dev laptop, pointed at a local test backend**
      (127.0.0.1, never production): 0.15.0 installed as the `AstraAgent` service and
      enrolled. Within one cycle the backend showed the real state: Defender pass (real-time
      on, signatures current), firewall fail (off on all three profiles), BitLocker fail (not
      encrypted). Security score 56%.
    - **Not done:** the "Defender off → fails within one cycle" check. Tamper Protection is on,
      and Set-MpPreference cannot turn real-time off with it on. Turning it off means changing
      a security setting, so it was not done without your say-so. The backend path for a
      real-time-off report is covered by `test_security_posture.py`.
    - **Still to do:** uninstall the agent from this laptop (the user will do this), and the
      tag. `agent-v0.15.0` triggers the release workflow, which auto-updates every enrolled PC,
      so it waits until phase-2 is merged to main. `agent-v0.15.0` triggers the
    release workflow, which auto-updates every enrolled PC, so it waits until phase-2 is merged
    to main and the decision is made.

**2a+ · Security fix actions** (follows F1; each action is its own change)
Today the Security Score shows a failing check but offers no fix. These add the first fixes,
one at a time, in this order. Every action needs: a backend registry entry, the same id in the
agent's `SystemRemediationExecutor` allowlist, a tier, a test that keeps the two in step, and
an update to `marketing-service/brand/claims.yaml` and the website action count.

- **Firewall: turn a profile on** (first, lowest risk). Agent runs `Set-NetFirewallProfile`
  for one named profile. Tier `approval_required`: turning it on can break a line-of-business
  app, so a person approves. Done when: a profile that is off goes on after approval, and the
  Security Score recovers in one cycle.
- **Defender: turn real-time protection on.** Only when Defender is the sole antivirus (no
  third-party AV registered, passive mode not in use). Tier `admin_only`. Done when it is
  refused on a machine with a third-party AV, and works on one without. Tamper Protection
  is never changed by SAVIO: if it is on, the action reports that and stops.
- **BitLocker: turn on the system drive.** Last, and only after recovery-key escrow exists.
  Needs TPM, a reboot, and the recovery key stored where an admin can get it (SAVIO or Entra
  ID / AD) before encryption starts. Tier `admin_only`. Not one click. Done when a key is
  escrowed, encryption completes, and the escrowed key opens the drive.
- **Built (16 Nov):** `enable_firewall` (approval_required, system) reads the state back
  and reports success only when all three profiles are on. Its failing firewall check and
  Fleet Issue link to it. `enable_defender_realtime` (admin_only, system) runs only when
  Defender is the sole registered antivirus, reads real-time back, and never touches Tamper
  Protection. BitLocker is still not built (needs key escrow first).
- **BitLocker key escrow, backend (16 Nov):** migration `0080` `device_bitlocker_keys`, the
  password encrypted with `app.core.crypto`. `POST /agent/bitlocker-keys` (device token; the
  device comes from the token, never the body; 503 and nothing written without the platform
  key). `GET /devices/{id}/bitlocker-keys` lists drive and key ID only (admin).
  `POST .../reveal` (admin, not view-as) returns the password and audits it. 9 tests; migration
  checked up / down / up on Postgres with a real insert.
- **BitLocker key escrow, agent (16 Nov):** `BitLockerKeyCollector` reads only the
  numerical-password protector (type 3) of drives BitLocker protects, checks its format, and
  never logs it. Uploaded with the hourly inventory, in batches of 10, and only keys not yet
  escrowed in this run. 348 agent tests pass. Not live-checked: this laptop has no
  BitLocker-protected drive, so there is no key to read.
- **Portal (16 Nov):** device page, admin-only "Recovery keys" tab. It lists drive, the 8-char
  Key ID the recovery screen shows, and when the key was escrowed. Reveal asks first ("this
  is recorded in the audit log"), then shows the password with Copy. The password lives only in
  the dialog's state. Checked on screen with a made-up key: list, confirm, reveal. The audit
  rows (escrow, reveal "by" the admin) hold no password.
  **Still to do:** a live check on a BitLocker-protected PC, and only then the turn-on action.
- **Security review (16 Nov, two parallel reviews):** no Critical. Fixed the same day:
  - **Escrow, High:** a replaced platform key left every stored key undecryptable and never
    re-escrowed. Now a re-sent key whose stored copy no longer decrypts is re-escrowed and
    audited (`device.bitlocker_key_re_escrow`).
  - **Escrow, Medium/Low:**
    - A different password for a known key is kept out and audited as a conflict.
    - At most 64 keys per device.
    - The agent endpoint no longer returns 422 bodies that echo a password.
    - Reveal is limited to 20 per admin per hour (429) and sent with `Cache-Control: no-store`.
    - Device delete records how many keys went with it.
    - The agent trims before sending, reads keys for drives whose protection is suspended,
      isolates errors per volume, and re-sends after a re-enrollment.
  - **Fix actions and posture:**
    - Firewall state is read from the effective `ActiveStore` through WMI, so a Group Policy
      that keeps it off is no longer reported as fixed, and non-English netsh text no longer
      matters. Checked live: it reads OFF on this laptop, matching netsh.
    - `enable_firewall` refuses beside another registered firewall.
    - A firewall with only some profiles reported is `unknown`, not pass.
    - Posture reports a third-party antivirus (migration `0081`), and the Defender check
      passes in that case.
    - `enable_defender_realtime` sets the preference through WMI, with PowerShell by full
      path only as a fallback.
    - Defender's Fleet Issue now links its fix.
  - **Not fixed (by design or later):** a dedicated "read BitLocker keys" permission, and
    notifying other admins on reveal.
- Each action's chat lines live in `_TECHNICAL_OUTCOME` and `_ACK_SUBJECT`
  (`remediation/service.py`); `test_chat_progress_message.py` fails if one is missing.
- Until these ship, the portal says "fix it in Intune or Group Policy" for these three checks.

**C3 · Hijack-proof AI** 🔒
- Mark every tool result that carries free text from outside (event messages, KB articles,
  user chat) as untrusted. A proposal whose justification relies on untrusted text is raised
  to `approval_required` regardless of the action's own tier.
- Red-team test suite: event-log and KB payloads that try to trigger actions; must all fail.
- "AI Safety" report: proposals made, raised, refused, and why.
- **As built (16 Nov, branch `phase-2`, not pushed):** `app/services/ai/untrusted.py`.
  - **Untrusted tools:** event log, knowledge base, installed apps and Windows updates. Their
    results reach the model labelled `untrusted_content`, with a notice that this is evidence
    and never instructions. They still arrive as tool results and never enter the system
    prompt. The expert brief says the same thing.
  - **When a fix is held:** the engine keeps a per-turn record of what the user said and what
    outside text was read. A fix is held when that outside text (compared after JSON
    decoding):
    - names the fix's id, or
    - supplies one of its free-text values (printer path, mail address, folder), or
    - reads like instructions (a short pattern list).
  - A free-text value the user never typed is held even when nothing outside was read.
  - **What "held" means:** the task goes to the approval queue, even for an `automatic`
    action. The approver sees SAVIO's own note appended to the model's reason. Audit
    `remediation.create` carries `ai_guard` and `raised`. A tier is never lowered.
  - **Refusals:** an admin-only, operator-only or unknown action requested by the assistant is
    refused and audited as `ai.proposal_refused`.
  - **Report:** `GET /reports/ai-safety` (admin and technician), read from the audit log with no
    new table. The portal shows it as Reports → "AI safety", a tab only staff see.
  - **Red-team suite:** `test_hijack_proof_ai.py`, 19 tests. They cover injected events and KB
    articles, a quiet mail-rule payload with no instruction words, an approval-tier fix,
    admin-only / operator-only / unknown actions, and controls showing that real crash
    evidence and values the user typed still run on their own.
    - Bug found by the suite: outside text was compared in its JSON form, where a UNC path
      has doubled backslashes, so a planted printer path never matched. It is now compared
      as decoded text.
  - **Screen check:** checked against the local test backend with a scripted "hijacked" model.
    The tab showed 2 proposals, 1 run on its own, 1 held, 1 refused, with reasons. The held
    task's reason carries SAVIO's note.
  - **Known limit (`ponytail:` in the file):** prose that steers to an automatic fix without
    naming it or using instruction words still runs. Automatic fixes are reversible by
    definition. Upgrade path: an org setting that holds every fix in a turn that read
    outside text.

**C1 · Proof-of-Fix**
- Capture an evidence snapshot before and after every remediation (the metric that
  triggered it); verify; schedule a 7-day recurrence check (per 2.0).
- Evidence card on the task page; feeds J5.
- **As built (16 Nov, branch `phase-2`, not pushed):** `app/services/remediation/evidence.py`,
  migration `0082` (adds a JSON column `remediation_tasks.evidence`).
  - **What is measured:** each measurable fix names the one number it was for:
    - free space on C: for the three clean-ups,
    - all three firewall profiles on, for `enable_firewall`,
    - Defender real-time protection, for `enable_defender_realtime`,
    - outstanding updates, for `windows_update_install`,
    - the named service running, for `restart_service`.
  - Fixes with nothing to measure (restart Outlook, flush DNS) carry no evidence. The portal
    says "Nothing to measure" for them rather than implying a result.
  - **Before** is read at dispatch. **After** comes from the first push collected after the
    agent reported success that carries that kind of data. A push collected earlier and
    delivered late from the offline queue is not used. Verdict: improved / no change / worse
    / not measured. Free space has 0.1 GB of noise allowance.
  - **7-day recheck** comes from the first such push a week on: does the fix still hold
    against the "before"?
  - **No scheduler needed.** All of it rides on the agent's own pushes, so C1 needs nothing
    from the 2.0 decision. A PC that stays offline is not rechecked, which is accurate.
  - **Portal:** the self-healing history has a "Proof" column ("6.2 GB → 9.3 GB Improved ·
    held for 7 days").
  - **Checked:** `test_proof_of_fix.py`, 7 tests, covering clean-up, firewall, late push,
    the recheck catching a comeback, a fix with no metric, and no before reading.
  - Migration checked up / down / up on Postgres, with a write and read-back and no column
    differences.
  - Run end to end over HTTP on the local test backend: 6.2 → 9.3 GB, improved, shown in
    the portal.
  - **Not done:** J5 does not read it yet (J5 is 2e).

**C2 · Canary rollout** 🔒
- On top of A4 deployments: waves (1 device → 10% → rest), a health gate between waves
  (task success + no new critical events), auto-halt on failure.
- "Undo" only where an inverse action exists (block↔unblock USB, disable↔enable account);
  otherwise halt-only, and the UI says so.
- **As built (16 Nov, branch `phase-2`, not pushed):** in `app/services/deployments.py`, plus
  migration `0083` (adds `waves`, `current_wave`, `wave_started_at`, `halted_at` and
  `halt_reason` to deployments).
  - **Waves:** a push to more than one PC goes in waves by default (`canary: false` gives the
    old all-at-once push). Wave 1 is one PC, an online one when there is one. Wave 2 is 10%,
    at least one PC. Wave 3 is the rest.
  - A wave's tasks are created only when it is released. A PC in a later wave has nothing
    queued until the gate opens.
  - **Gate:** the next wave opens only when all three hold:
    - every task in the current wave has finished, and none failed;
    - no PC in the wave has logged a **Critical** event since the wave started (Error-level
      events are too routine on Windows to gate on);
    - 10 minutes of soak time have passed since the last one finished.
  - The gate is checked when a wave PC reports a result and on its telemetry pushes, so no
    scheduler is needed.
  - Each wave is approved in the creator's name, and `create_task` re-checks their authority.
    If they have been demoted or deactivated since, the rollout halts.
  - **Halt:** on a failure or a Critical event the rollout halts on its own. Installs queued
    but not yet started are cancelled ("Not run"), and later waves are never created. There
    is an audit row and a critical notification.
  - Staff can halt by hand with a reason, and resume, which releases the next wave at once.
    Both are audited.
  - **Undo:** halt-only. SAVIO has no inverse of "install a package", and the portal says so
    on the Halt button. Deployments still push installs only. When they can carry an action
    with an inverse (USB block/unblock, account disable/enable), undo goes there.
  - **Portal:** Software page:
    - a "Roll out in waves" option, on by default;
    - each push shows its wave ("Wave 1 of 3 · 11 PCs wait for the health check"), or a
      red halted bar with the reason and a Resume button.
  - **Checked:** `test_canary_rollout.py`, 6 tests: the wave plan, waves opening in order, a
    failure halting, a Critical event halting and cancelling queued installs, halt and resume
    by hand, and a one-PC push.
  - The A4 test now asks for all-at-once explicitly.
  - Migration checked up / down / up on Postgres.
  - Live on the local test backend with 12 made-up PCs: one push held at wave 1 with 11
    waiting; a failing canary halted the second. Both shown on screen.

**J1 / J2 / J5 · AI IT Manager core**
- J2 Recommendations: `recommendations` table (evidence, impact in ₹/risk/time, effort,
  linked action); generated from F1, L2, assets, telemetry; dismiss with reason.
- J1 Brief: daily (admin) and weekly (owner) summary email; business language; Hindi option.
- J5 Value report: hours saved (auto-fixed tasks × configured minutes), incidents prevented,
  ₹ saved — every number traceable.
- **As built, J2 + J5 (16 Nov, branch `phase-2`, not pushed):** migration `0084` adds the
  `recommendations` table and two org settings: `minutes_per_fix` (default 15) and
  `it_hourly_cost` in ₹ (unset by default, and 0 clears it).
  - **No ₹ is ever estimated.** A rupee figure is the org's own hourly cost times a counted
    amount of work. With no cost set, no rupee figure appears anywhere.
  - **J2 Recommendations** (`app/services/recommendations.py`) are rebuilt from live data on
    every read, so no scheduler is needed (option b). Sources:
    - failing compliance checks (F1 security and L2 activation included), worded as in Fleet
      Issues / the Health Check, with the fix action when one exists;
    - disks forecast to fill;
    - warranties ending within 90 days, or ended in the last 30;
    - PCs older than 4 years.
  - Each recommendation carries its evidence (the PCs, named), a risk, an effort (one click /
    hands-on / purchase), and by-hand time (PCs × minutes per fix) with its working.
  - **Lifecycle:** dismiss needs a reason and is audited; restore brings it back. A finding
    that clears is marked resolved, and the dismissal ends with it. If it comes back, it
    reopens.
  - Portal: Operations → Recommendations (staff), with tabs for open, dismissed and resolved.
  - **J5 Value report** (`GET /reports/value`, staff) counts fixes that succeeded with
    **nobody approving them**. A fix a person approved is their time, not SAVIO's saving.
    - Hours = fixes × minutes per fix. ₹ = hours × hourly cost.
    - "Proven to work", "held 7 days" and "came back" are C1's own verdicts.
    - Each card shows its basis, and every fix behind the numbers is listed.
  - Portal: Reports → Value. Settings → "Value figures" holds the two numbers.
  - **Checked:** `test_recommendations_value.py`, 3 tests:
    - lifecycle: appear, rupees with the working, dismiss (403 / 422 / audit), resolve,
      reopen;
    - restore;
    - value counting only unattended fixes in the window, and ₹ appearing and disappearing
      with the setting.
  - Migration checked up / down / up on Postgres with a write; no column differences on the
    new table.
  - On the local test backend, the real laptop's firewall-off shows as the top
    recommendation. Both pages checked on screen.
  - **J1 Brief waits for the 2.0 decision.** It sends e-mail on a clock, so it needs a
    scheduler; J2 and J5 do not.
- **As built, J1 (16 Nov, on demand per the 2.0 decision):** `app/services/brief.py`.
  - **Endpoints:** `GET /reports/brief?period=day|week`, and
    `POST /reports/brief/email` for staff. The e-mail goes to the person asking, and only
    to them, never to a typed-in list. It is audited (`report.brief_emailed`) and limited
    to 5 an hour.
  - **Content:** plain business language, in English only. A Hindi version was built and
    then removed at the user's request (16 Nov), so the roadmap's "Hindi option" is not in
    J1. Every line is a count from SAVIO's own records:
    - computers: how many, how many online, how many new;
    - the security score (F1);
    - fixes run with nobody involved, and the hours and ₹ they saved (J5);
    - fixes that failed, or are waiting for approval;
    - PCs silent for over a day;
    - AI suggestions held or refused (C3);
    - rollouts halted (C2);
    - warranties ending within 30 days;
    - the top three recommendations (J2).
  - No sentence is written by a model. The e-mail HTML escapes every value.
  - A scheduler can later call `build` and `send` unchanged.
  - **Portal:** Reports → Brief, with Today / This week and "Email it to me".
  - **Checked:** `test_brief.py`, 4 tests:
    - the day's counts and wording;
    - a just-enrolled PC is not counted as silent, and a PC quiet for two days is;
    - week against day;
    - an unknown period is refused;
    - e-mail goes only to the asker, escaped, audited, with a 409 on the sixth, and 403 for
      a plain user.
  - On screen against the local test backend. "Email it to me" says plainly when e-mail is
    not set up.

**Security review, second pass (16 Nov):** covered the BitLocker reveal tab, C3, C1, C2 and
J2/J5. No Critical findings. Fixed the same day: four Medium and all nine Low (migration
`0085`).
- **C3:**
  - **Tool coverage (M1).** The list is now of *trusted* tools: SAVIO's own
    `propose_remediation` and the two ticket tools. Every other tool's result is outside
    text, including compliance details, device and drive names, and any tool added later.
  - **Earlier turns count (M2).** The guard now reads the untrusted outputs stored in the
    chat's earlier tool trails. So "read a planted line, ask 'shall I?', user says yes" is
    held.
  - **Laundered values (M2).** A value that appears in outside text is held even after the
    user types it.
  - **Normalisation (L1).** Text is normalised before matching: NFKC, zero-width characters
    dropped, and `_`, `-` and spaces treated alike.
  - **Free-text parameters (L2).** Every parameter not on the allowlist (service, process,
    time zone, KB) counts as free text.
  - **Hold reasons (L3, L4).** They live in their own `remediation_tasks.ai_guard` column,
    shown separately in the approval queue, not appended to the model's reason. A held fix
    is never learned into a replayable fix.
  - **Still not folded:** look-alike letters from other scripts (Cyrillic "а").
- **C2:**
  - **Resume (M3).** Resume needs the resumer's own authority to approve the action. The
    next wave is approved and audited in their name.
  - **Halt races (M4).** A halt is one conditional `UPDATE`, which also cancels tasks
    waiting for approval. The agent's claim is conditional too, so halt and claim can never
    both win. `create_task` locks the deployment row and refuses a task for a halted rollout,
    so a wave queued during a halt stops where the halt landed.
  - **Locking and crashes (L7).** The deployment lock re-reads the row. A crash part-way
    through a wave halts the rollout instead of leaving it half-queued.
- **C1:**
  - **Claim fencing (L5).** A failed "before" reading no longer blocks the claim.
  - **Reads (L6).** `observe` decides what a push is for before reading, and takes the
    oldest tasks first.
- **J2 (L8):** two staff loading Recommendations together no longer get a 500.
- **BitLocker (L9):** a copied key is cleared from the clipboard after a minute, if it is
  still there.
- **Noted, not code:** Proof-of-Fix and "proven" are the device's own report, so wording
  shown to customers must say so.

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
- **As built, first slice (16 Nov):** `app/services/warranty.py`, migration `0086`.
  - **New asset fields:** `warranty_source`, `warranty_checked_at`, and a `warranty_found`
    date with its source, held while it waits for a choice.
  - **One rule for every source:** `apply_found` fills a blank date, or updates one that an
    earlier import or lookup set. A date a person entered is never replaced. That covers
    `manual`, and also an old date with no source, which a person typed before sources
    existed. A different date is held beside it, and the admin presses "Use it" or "Keep
    mine". Both choices are audited and written to the asset passport.
  - **Typing a date by hand** marks it `manual` and settles any date waiting for a choice.
  - **CSV import** (`POST /assets/warranty/import`, staff):
    - columns `serial_number` (or `serial`) or `asset_tag`, plus `warranty_expiry` (or
      `warranty_end`);
    - dates as YYYY-MM-DD or day-first DD/MM/YYYY;
    - matched within the org only and case-insensitive, and a serial matching two assets
      is skipped;
    - at most 1 MB and 5000 rows, audited.
  - **Portal:** Assets → "Import warranty CSV". The Warranty column shows the source and,
    when one is waiting, "CSV says …" with "Use it" / "Keep mine".
  - **Checked:** `test_warranty.py`, 4 tests. Migration checked up / down / up on Postgres
    with a write. Checked on screen: a day-first CSV date filled one asset; a different date
    for a hand-entered one waited; "Use it" took it.
  - **Not built yet:**
    - **Vendor connectors.** Dell TechDirect, the HP developer portal and Lenovo need
      approved API access, and **you have to apply for it**. Each will call
      `apply_found(asset, date, "dell_api")`, and nothing else changes.
    - **Invoice upload → AI extraction:** built since, below. Only the live model check is
      still to do.
    - **"Refresh warranty" and the weekly refresh.** They wait for a connector to refresh
      from, and for the scheduler.
- **As built, invoice reading (16 Nov):** `app/services/invoice_reader.py`, and
  `POST /assets/{id}/warranty/invoice` (staff).
  - **Upload:** a PDF, JPG or PNG up to 10 MB is read in the browser and sent as base64. It
    is never stored, and only the fields read go into the audit log.
  - **The call:** one Claude call (`invoice_ai_model`, default `claude-opus-5-5`) with the
    file as a document or image block. A JSON schema fixes the answer to these fields:
    vendor, invoice date, warranty end or months, total, serials. The server-side refusal
    fallback is on.
  - **The warranty date** is the end date the invoice states, or its date plus the months it
    states (capped at 120). It goes through `apply_found`, so a date typed by hand is never
    replaced. Purchase date and cost are filled only where the asset has none.
  - **Guard:** if the invoice lists serial numbers and the asset has one, it must be among
    them, otherwise the request is refused. Wrong invoice, right asset is the likely
    mistake.
  - **Portal:** an invoice button on each asset row.
  - **Checked:** in `test_warranty.py`, 5 more tests (9 in all):
    - a blank asset filled;
    - a hand-entered date kept as a conflict;
    - a serial mismatch refused;
    - "not stated";
    - no AI key gives 503;
    - a wrong file type gives 422;
    - a plain user gives 403;
    - the exact request sent to Claude (document block, schema, fallback);
    - a refusal reported, not parsed;
    - month arithmetic.
  - **Not done:** a live model run on a real invoice. It needs a dev Anthropic key in
    `backend/.env`.

**Security review, third pass (16 Nov):** covered J1, L5b (CSV and invoice) and N2. No
Critical findings. Everything was fixed the same day:
- **H1 (cost).** Invoice reads are paid calls, so they are now limited to 20 per person per
  hour and 100 per org per day. Every attempt is recorded before the call, so one that
  fails still counts. The client allows one retry and 60 s; `max_tokens` is 8000.
- **H2 (database pool).** The database connection is released while the model reads,
  instead of being held for the whole call.
- **M1 (provenance).** Saving an asset's other fields no longer relabels its warranty date
  "by hand" or drops a pending choice. Only a changed date counts as a person's.
- **M2 (bad dates).** Asset dates are validated on create and edit; day-first input is
  normalised. A malformed legacy date is skipped by the Watchlist instead of failing it.
- **Lows:**
  - The model's answer is validated with Pydantic: finite cost under 1e9, no extra fields,
    capped lengths.
  - An invoice never replaces *any* existing date, a CSV one included. It only fills a
    blank or raises a conflict.
  - Every SDK error is caught. The minimum SDK is pinned to 2.3.0, and a test sends the real
    request through the installed SDK with a mocked transport.
  - CSV handling: a malformed file gives a 400; rows are counted before any query; a
    serial twice in one file is refused instead of the last row winning; echoes are
    truncated.
  - A held conflict, or a dropped found date, writes a passport note.
  - The brief's rate limit counts the request before the slow send, so parallel requests
    can't slip past it.
  - The Watchlist fetches the agent manifest before opening a database transaction.
- **Not changed:** the invoice model stays `claude-opus-5-5`. Cost is now capped by the
  limits, and `invoice_ai_model` can be changed in config.

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
  - **As built, slice 1, agent writer (17 Nov, branch `phase-3`, not pushed):**
    `agent/src/AstraAgent.Service/Guard/`.
  - **`BrowserPolicy`** is the browser-neutral model. Every field is off by default:
    incognito off, extension developer mode off, all dev tools off, new profiles and guest
    off, blocked / allowed sites (host names), Google allowed domains (D2), and the
    extension's store IDs. `Validate()` refuses bad hosts, IDs and non-https URLs before
    anything is written.
  - **`BrowserPolicyMap`** gives each browser's own names:
    - Chrome: `IncognitoModeAvailability`, `BrowserAddPersonEnabled`;
    - Edge: `InPrivateModeAvailability`, `BrowserAddProfileEnabled`;
    - shared: `ExtensionDeveloperModeSettings`, `URLBlocklist` / `URLAllowlist`,
      `AllowedDomainsForApps`, `ExtensionInstallForcelist` with each store's update URL;
    - Firefox: `DisablePrivateBrowsing`, `DisableDeveloperTools`, `WebsiteFilter` match
      patterns, `ExtensionSettings` force_installed.
  - **`BrowserPolicyWriter`** owns only what it wrote. The names it set are recorded under
    `HKLM\SOFTWARE\SAVIO\BrowserPolicy\<browser>` (and `savio-owned.json` for Firefox),
    and only those are changed or removed.
    - A policy someone else already sets, such as an org's GPO, is reported as a
      **conflict** and never overwritten. That covers this laptop's existing
      `LocalNetworkAccessAllowedForUrls`.
    - Re-applying is idempotent. Tampering is **repaired and reported**; a local admin
      can't be stopped, only noticed.
    - Every write is read back, and one that doesn't stick is an error.
    - Firefox's policies.json is merged, never replaced. An unreadable file is left
      untouched, and writes are atomic.
  - **Checked:** `BrowserPolicyWriterTests` (12), against the real registry under a
    throwaway HKCU key (never HKLM) and a temp folder:
    - apply and idempotency;
    - a foreign policy kept, with a conflict reported;
    - tamper repaired;
    - shrink removes only what SAVIO set;
    - Edge names;
    - validation;
    - Firefox merge;
    - broken Firefox file left alone.
  - All 382 agent tests pass, and the real browser keys were untouched.
  - **As built, slice 2, end to end (17 Nov):**
    - **Backend:** new entitlement `ai_guard` (in no plan; an operator switches it on per
      org) and migration `0087`, with two tables:
      - `org_browser_policies`: one per org, with a version that goes up on each change;
      - `device_browser_policy_states`: each PC's last report.
    - **Admin endpoints:**
      - `GET`/`PUT /guard/browser-policy`. Editing is admin-only, staff can read, and
        changes are audited with the fields that changed.
      - `GET /guard/browser-policy/devices`.
      - Validation matches the agent's, and sites are normalised and de-duplicated.
    - **Agent endpoints:**
      - `GET /agent/browser-policy`. An org without `ai_guard` gets version 0 and an empty
        policy, so its PCs remove what SAVIO set.
      - `POST /agent/browser-policy/report`. The device comes from its token. A *repaired*
        entry (tamper) is audited and raises a "Browser policy tampered" notification.
    - **Agent:** `BrowserPolicyWorker`.
      - It fetches hourly and applies every heartbeat cycle, so a removed lock is back
        within a minute.
      - It reports when something changed, or when the version, conflicts or errors
        differ.
      - A failed fetch **keeps** the last policy and retries in 5 minutes. Only the
        backend's explicit "version 0, empty" removes it.
    - **Portal:**
      - AI Guard → Browser policy: the switches, blocked / allowed sites and Google
        domains, plus a per-PC table showing the version (with an "older" marker),
        errors, and conflicts ("set elsewhere, left alone").
      - An AI Guard toggle on the operator's org page.
    - **Checked:**
      - `test_browser_policy.py` (5): 402 without the add-on, version and audit,
        validation, roles, reports and tamper notification.
      - `BrowserPolicyWorkerTests` (4): cadence, unreachable backend, add-on off,
        re-enrolment.
      - All 386 agent tests pass. Migration checked up / down / up on Postgres with a
        write.
      - Checked on screen against the local backend, with a made-up device report: the
        policy is saved, version 2 comes from the portal, and the PC row shows "older", the
        Firefox error and the conflict.
    - **The agent was not run against this laptop's browsers:** it would change your Chrome
      and Edge. That is the VM test.
  - **Then a live VM test (Spike 2):** which of these policies Chrome and Edge honour on a
    PC not joined to a domain.
  - **As built, slice 3, blocking by category (18 Nov):**
    - **Six categories,** fixed in `browser_policy.SITE_CATEGORIES`: personal file-sharing,
      personal e-mail, AI chat, messaging on the web, social media and paste sites.
      - Each names the personal service, never a shared parent that businesses also use:
        `outlook.live.com`, not `live.com`; `web.whatsapp.com`, not `whatsapp.com`.
      - Gmail and Drive are not in the list; D2's Google domains handle them.
    - **Choosing:** an admin ticks categories (`blocked_categories`) under the blocked sites.
      "Always allowed" still wins, for example linkedin.com for a sales team.
    - **Served as one block list:** the PC gets the typed sites plus each category's hosts,
      de-duplicated, with at most 500 in total, checked when the policy is saved. The agent
      did not change.
    - **The hosts are copied when saved** (`category_hosts`, migration 0094). A list changed
      in a later release reaches a PC only when the policy is saved again, as a new version.
      The PC is never served words nobody saved, and the version-based tamper check stays
      right.
    - **Suggestion:** "Block personal file-sharing sites" now ticks the category instead of
      adding six hosts.
    - **Checked:**
      - `test_blocking_by_category`: the category list, the merge and de-duplication, the
        category not sent to the PC, allowed sites kept, a changed list served only after a
        save (as version 2), the 500 limit, an unknown category refused;
      - the suggestion tests;
      - migration 0094 up/down/up, with an existing row given an empty list;
      - on screen: two categories ticked and saved as version 14, with 21 hosts stored.
  - **As built, slice 4, company accounts beyond Google (18 Nov, Spike 1 answered):**
    - **The finding:** these services enforce "own accounts only" themselves when a request
      carries their header. The vendors assume a TLS-inspecting proxy adds it; an extension
      can add it instead. Checked live in a throwaway Chrome profile:
      - every header reached the server as set, including `sec-` ones (echoed by
        httpbin.org);
      - Microsoft's sign-in read `sec-Restrict-Tenant-Access-Policy` at once and refused a
        made-up tenant (AADSTS1000107);
      - ChatGPT and Claude showed nothing to a signed-out visitor: their check applies when
        someone signs in to a workspace or organization, which needs a real account (the pilot);
      - the older Microsoft header (`Restrict-Access-To-Tenants`) acts only at sign-in, so the
        newer tenant restrictions v2 is used instead.
    - **Services and headers** (each from the vendor's own docs):

      | Service | Header | Sent to |
      |---|---|---|
      | Microsoft 365 | `sec-Restrict-Tenant-Access-Policy: <tenant>:<policy>` (tenant restrictions v2) | login.microsoftonline.com, login.microsoft.com, login.windows.net, login.live.com |
      | Claude | `anthropic-allowed-org-ids` | claude.ai, claude.com, anthropic.com |
      | ChatGPT Enterprise | `ChatGPT-Allowed-Workspace-Id` | chatgpt.com, chat.openai.com |
      | Slack (Business+ / Enterprise) | `X-Slack-Allowed-Workspaces-Requester`, `X-Slack-Allowed-Workspaces` | slack.com |

      Dropbox was dropped: its header name is not published.
    - **Policy:** `microsoft_tenant_id` + `microsoft_policy_id`, `claude_org_ids`,
      `chatgpt_workspace_ids`, `slack_requester_id` + `slack_allowed_ids`.
      - Only IDs of the right shape are accepted, at most 50 per service, and the pairs come
        both or neither. This is checked by the backend, by the agent, and again by the
        extension, because these become request headers.
      - Without the extension the IDs are refused, so the setting is never silently off.
    - **Agent:** passes them to the extension as managed settings, only when set.
    - **Extension:** `accounts.js` turns the settings into `declarativeNetRequest` rules that
      *set* (never append) each header on that service's domains only. The service worker
      keeps them in step with the policy: at start, on install, and whenever the managed
      settings change. The manifest gains `declarativeNetRequest`, and its description says so.
    - **Portal:** a "Company accounts only" section with where to find each ID.
    - **Checked:**
      - backend `test_company_accounts_only`;
      - agent `Company_account_ids_go_to_the_extension_only_when_set_and_only_as_ids`
        (a smuggled `\r\n` header is refused);
      - extension `accounts.test.mjs` (3);
      - live: the real extension started with no rules, Chrome accepted the generated rules,
        and Microsoft read the header;
      - on screen: the refusal without an extension ID, and saved IDs shown back.
    - **Not checked:**
      - that the rules are cleared when the extension restarts with no policy: the service
        worker went to sleep before it could be read;
      - each service blocking a real personal account: that needs the org's own accounts.
    - **Limit:** an extension can only cover the browser. A desktop app (Teams, Slack,
      ChatGPT) does not pass through it. Windows' own tenant restrictions v2 setting covers
      Microsoft's apps; it is a later step.
  - **As built, slice 5, a policy per device group (18 Nov):**
    - **Shape:** the org's policy stays the default for everyone. An admin can give a device
      group a complete policy of its own, which starts as a copy of the default
      (`group_browser_policies`, migration 0095).
    - **One policy per PC, never a merge.** Groups overlap, so a PC in several groups with a
      policy gets the one with the lowest priority number (ties: group name). A PC in none
      gets the default. The agent did not change.
    - **Version numbers are never reused.** One sequence per org (`org_browser_policies.seq`)
      numbers every saved change, the default's or a group's. A number therefore names exactly
      one policy's content.
      - A PC moved into or out of a group, or a group policy removed, always reports a new
        version, so the tamper check counts it as an update.
      - Re-ranking changes which policy a PC gets without a new number, because each number
        already names its content.
    - **The same rules as the default:** the E8 pilot holds group policies to record-only
      too, categories are copied on save, and every change is audited
      (`guard.group_policy_update` / `_delete`). A group policy needs the default to exist
      first.
    - **Deleting the group** removes its policy (cascade), and its PCs go back to the
      default.
    - **Portal:**
      - "Policy for: Everyone · <groups>" above the form, which then edits that group's policy;
      - "+ A policy for a group…" for groups without one;
      - a priority box and "Remove this group's policy";
      - the PC table gains a Policy column, and "older" now compares a PC with its own
        policy.
    - **Checked:**
      - `test_group_policies`: needs the default first, the pilot, the winner by priority,
        re-ranking without a new version, the default taking the next number, the PC row's
        policy, technician refused, removal sending PCs back, 404s, the audit;
      - migration 0095 up/down/up, with an existing row given `seq` = its version;
      - on screen: Sales team given a copy plus "Social media", saved as version 16 after the
        default's 15, and "Everyone" still showing the default.
  - **As built, slice 6, other browsers (18 Nov):** the last D1/D2 piece. Nothing above
    reaches a browser other than Chrome, Edge and Firefox.
    - **Which:** Brave, Opera (and GX), Vivaldi, Yandex, Tor Browser, Chromium, Waterfox,
      LibreWolf. A fixed list in the agent (`OtherBrowsers.cs`) and the backend
      (`OTHER_BROWSERS`), kept in step.
    - **Seen:** the PC table shows "Other browsers installed: …" from each PC's app inventory
      (machine and per-user installs), linking to the PC. No agent change was needed for this.
    - **Closed:** a policy switch, "Close other browsers" (`block_other_browsers`, off by
      default). The agent's `OtherBrowserBlocker` checks running processes every 2 s and closes
      a match:
      - a match needs the exe name *and* the browser's name in the file's company, product or
        path, so Google Chrome, an unrelated `browser.exe`, or a file it cannot read is left
        alone;
      - the person gets a Windows message, at most once a minute per browser and session, naming
        the browser and saying to use Chrome, Edge or Firefox (fixed text, never from the server);
      - one start counts once, however many processes it has. Counts go with the next policy
        report (`closed`, sent only when there are some, so an older backend never sees the
        field), are kept if the report fails, and the backend audits each report as
        `guard.other_browser_closed`. Only known names are accepted.
    - **Not automatic: uninstall.** Removing one stays the admin-only "Uninstall software" action
      from the PC's Software tab, decided by a person. That action removes machine-wide installs
      only; most of these browsers install per user by default, so closing is what reaches them.
    - Not held by the E8 pilot, like blocked sites: the pilot is about the extension's mode.
    - **Checked:** `test_other_browsers` (served, listed from inventory without matching
      "Operations Manager", audited, a zero dropped, unknown names refused); agent
      `OtherBrowsersTests` (11 match cases including Chrome, Firefox and an unknown
      `browser.exe` left alone; closed only when asked, once per start, one notice a minute,
      reported once, kept after a failed report, nothing while dormant); agent suite 440; on
      screen against the local backend: a PC with Opera GX and Brave in its inventory showed
      both, and the switch saved as version 17.
    - **Not checked:** closing a real Opera on a PC. The process list, kill and notice were
      replaced in tests; that is a VM test.
  - **As built, slice 7, Microsoft 365 on the PC (18 Nov):** company-account-only for the
    desktop apps, not only the browser. The extension's header (slice 4) covers browsers;
    Outlook, Teams, Word and the rest sign in outside them.
    - **How:** Windows' own tenant restrictions v2, the Group Policy "Cloud Policy Details"
      (`TenantRestrictions.admx`, shipped with Windows): `tenantid` and `policyid` as strings
      under `HKLM\SOFTWARE\Policies\Microsoft\Windows\TenantRestrictions\Payload`. Value names
      and types read from the ADMX on this laptop. Per Microsoft it covers all Office apps,
      UWP apps, and Edge with every site in it, for sign-in and for SharePoint, Exchange and
      Graph data; not Chrome, Firefox or .NET apps (the extension covers the browsers).
      Windows 11, or Windows 10 2004 or later with KB5006738. Microsoft still calls the Windows
      method "preview".
    - **Switch:** `microsoft_on_windows` ("Microsoft 365 on the PC too"), off by default,
      using the two IDs already on the form. It needs no extension; the other services still
      do.
    - **Never `enforceFirewall`:** Microsoft warns that without a matching App Control policy it
      cuts every app off from Microsoft's endpoints. Hostnames and IP ranges are left blank,
      as Microsoft's own test steps say.
    - **Writer:** the registry writer Chrome and Edge use (ownership list under
      `SOFTWARE\SAVIO\BrowserPolicy\Windows`, repair, read-back), reported as "Windows". The
      payload is one policy, so all or nothing: if Intune or a GPO already sets any part of it,
      SAVIO writes none of it and shows a conflict. Turned off: SAVIO's values and the keys
      they leave empty are removed.
    - **Risk, said on the page:** a wrong ID stops Office signing in on every PC that gets it;
      try it on one group first (slice 5).
    - **Checked:** agent test against a throwaway HKCU key (nothing created when unused, the two
      strings, no `enforceFirewall`, repair, removal with empty keys pruned, someone else's
      payload left alone and reported); backend (needs the IDs, no extension needed, served,
      a "Windows" report row kept); agent suite 448; on screen against the local backend:
      switched on and saved as version 18.
    - **Not checked:** Windows actually enforcing it. Not on this laptop: a test tenant ID
      would stop its real Office sign-ins. That is the VM test, with a real Entra tenant
      (Event Viewer → Microsoft → Windows → TenantRestrictions → Operational).
- **D3 Extension + native host** 🔒: MV3 extension intercepts paste, file input,
  drag-and-drop, form submit on watched sites; talks only to the local agent via native
  messaging (policy offline, device identity).
  - **As built, slice 1 (16 Nov, branch `phase-3`):**
    - **Native host:** `agent/src/AstraAgent.GuardHost`, an exe called
      `savio-guard-host.exe` that speaks Chrome/Firefox native messaging (4-byte length + JSON,
      16 MiB cap) and wraps the D4 scanner. It answers with counts, the contact-list flag and
      keyword *indexes* only, never the text. Anything other than a scan request is refused;
      a malformed or oversized frame ends the connection.
    - **Extension:** `extension/`, MV3, one codebase for Chrome, Edge and Firefox. The
      content script catches paste, drop, file choice and form submit (capture phase); the
      service worker asks the host; `decide.js` turns the answer into allow / warn / block. It
      keeps the last 200 events, counts only, in local storage.
    - **Safe defaults:** log-only unless the admin chooses otherwise; e-mail addresses are
      counted but never acted on; a scanner that cannot be reached or timed out is never
      "clean", and warns rather than blocks.
  - **As built, slice 2 (16 Nov):**
    - **Shipped with the agent:** a `PublishGuardHost` target in the service project
      publishes the host into the same folder, so the release workflow, the installer build and
      `-BuildFromSource` all carry it without a script change. Checked with a publish to a
      temp folder.
    - **Settings from the portal:** mode, sites to check, restricted keywords and
      count-but-ignore kinds are part of the browser policy (`guard_*` fields), validated in
      the backend and again on the PC. The audit records which fields changed, never the
      keywords.
    - **Handed to the extension as managed policy:** Chrome and Edge under
      `3rdparty\extensions\<id>\policy`, Firefox under `3rdparty.Extensions.<id>` in
      policies.json. The writer now handles nested policy names: it owns only our extension's
      branch, leaves other extensions' 3rdparty settings alone, prunes what it emptied, and
      treats settings someone else wrote for our ID as a conflict.
    - **Host registration:** while the policy forces the extension in, the agent registers
      `com.savio.guard` for that browser (HKLM NativeMessagingHosts → a manifest naming the
      exe and the one extension allowed to start it). The manifests sit in the install folder,
      where only administrators can write. Removed when the extension no longer is; repointed
      if someone changes it; an error if the exe is missing.
    - **Checked:** writer tests for 3rdparty (beside another vendor's, drift, conflict,
      pruning, Firefox), guard-setting validation, host registration (manifest contents,
      repoint repaired, removal), backend validation and audit. Nothing was written to this
      laptop's HKLM or real browsers.
  - **Not yet:** store listing (extension IDs), a live browser test on the VM, sending the
    extension's events to the backend (E3), and the D7 dialogs.
- **E4 Scanner isolation** 🔒: content analysis runs in a separate process with outbound
  network blocked by firewall rule; it talks to the agent over a fixed schema with **no
  free-text field** (category, counts, site, action, hashes of files only).
  - **As built (17 Nov, branch `phase-3`):**
    - **The fixed schema** is E3's `GuardEvent`: unknown fields are refused at the host, the
      service and the backend.
    - **The scanner process** is `savio-guard-host.exe`, started by the browser, with no
      network code.
    - **New, `ScannerFirewall`:**
      - two Windows Firewall rules block that exe outbound and inbound, on every profile,
        while any browser is made to run the extension;
      - checked every cycle; a deleted or switched-off rule is put back and reported, and
        every write is read back;
      - when no extension is forced, only SAVIO's two rules are removed;
      - set through Windows Firewall's own COM interface (HNetCfg.FwPolicy2), not netsh text.
    - **SAVIO never turns the firewall on.** That is the organization's setting, as in
      FirewallRemediation. When Windows Firewall is off, or another firewall is registered,
      the rules are kept and the report says plainly that the block is not enforced (and
      where to set it instead).
    - **Reports:** reported as "Scanner" beside the browsers. The portal's per-PC status
      shows "Scanner's network block: …".
    - **Checked:**
      - `ScannerFirewallTests` (4) against an in-memory rule list: both directions and all
        profiles, idempotent, case-blind paths, repair of a deleted or disabled rule,
        "did not stick", the not-enforced message, and only our rules removed;
      - the COM property names were read (only read) on this laptop. Its firewall was not
        changed.
  - **Not yet:** a live run on the VM (the rules set by the real service, and a test that the
    host really cannot connect).
- **E3 Outbound Ledger:** readable local copy of everything the agent sends + portal page.
  - **As built, slice 1, the event path (17 Nov, branch `phase-3`):**
    - **What travels:** the extension → its native host → the service's pipe
      `SAVIO.GuardEvents` → `POST /agent/guard/events` → AI Guard → "What was found".
    - **Schema:** fixed, `AstraAgent.Guard.GuardEvent`. It holds a host name, channel, mode,
      decision, counts per kind, a contact-list flag, a keyword-hit count and a could-not-check
      flag. Unknown fields are refused at the host, the service and the backend, so text cannot
      ride along under another name. The host builds the event from those fields, never from
      the raw message.
    - **Only notable events:** something found, or could not check. An ordinary paste is not
      recorded at all.
    - **Who:** the service takes the person from Windows. The host connects at Identification
      level, and an anonymous client is refused. The host writes only to a pipe owned by
      SYSTEM (same ACL as Fix-my-internet), so another user's squatting pipe gets nothing.
    - **Bounds:**
      - at most 120 events a minute and 5,000 queued;
      - batches of up to 500, sent every minute;
      - kept until the backend has them;
      - a 422 is dropped rather than retried forever.
    - **ponytail:** the queue is in memory, so a service restart loses what was not sent.
      Upgrade path: an append-only file in the service's data folder.
    - **Backend:** table `guard_events` (migration 0088); events kept 180 days, pruned per
      device on ingest. Clock errors are dropped. An org without `ai_guard` has its events
      accepted and dropped.
    - **Who can read:** summary and list are **admin only**, because they name people.
    - **Bug fixed on the way:** the host answers `contact_list` / `keyword_hits`, and the
      extension was reading camelCase names. Contact lists and keywords never triggered a
      warn or block. `fromHost()` now reads the host's shape, and a test covers it.
    - **Checked:**
      - `GuardEventTests` (5), including a real pipe: the user comes from Windows, an
        anonymous client is refused, junk is dropped;
      - extension tests (8);
      - backend `test_guard_events` (5);
      - migration 0088 up/down/up on Postgres with a real write, and no model drift;
      - the page on screen, with sample events, against the local backend.
  - **As built, slice 2, the ledger (17 Nov):**
    - **Outbound Ledger:** a handler on the agent's API client writes one JSON line per
      request (time, method, path, status, bytes, body). The bytes recorded are the bytes
      sent: the body is buffered once.
    - **Where it lives:** `state\ledger\ledger-YYYY-MM-DD.jsonl` beside the install folder,
      readable by SYSTEM and Administrators only, kept 14 days. Bodies stop after 20 MB a
      day; lines carry on.
    - **Never written:**
      - headers, so never the device token;
      - the BitLocker escrow body: the line records the call and its size only;
      - any property named like a password, token or secret;
      - any string shaped like a recovery password, wherever it sits.
    - **Robustness:** a failed request is still written down (status empty). The ledger fails
      closed on a folder it cannot lock down and never blocks a request.
    - **Persistent event queue:** `state\guard-events.jsonl` is appended as events arrive,
      rewritten when the backend takes a batch, and read back and re-checked line by line on
      start. A torn or edited line is skipped. This replaces slice 1's in-memory ponytail.
    - **Checked:**
      - `OutboundLedgerTests` (4): bytes match, the escrow body and secrets never reach disk,
        a failure is recorded, pruning;
      - a queue restart test;
      - all 408 agent tests.
  - **Not yet:**
    - the outcome after a warning (went ahead or not), which comes with D7;
    - a portal view of what each PC sent;
    - the remote-support (MeshCentral) traffic and update downloads, which do not go through
      the API client and so are not in the ledger.
- **D4 Detectors:** Aadhaar (Verhoeff), PAN, GSTIN, card (Luhn), +91 mobile, email,
  IFSC+account; bulk/structured "contact list" detection; admin keywords.
  - **As built (16 Nov, branch `phase-3`, not pushed):** new library
    `agent/src/AstraAgent.Guard`. It has no dependencies and does no I/O, so the E4 isolated
    scanner process can host it.
  - **`PiiScanner.Scan(text, keywords)`** returns counts per finding, a contact-list flag,
    keyword hits *by index*, and Truncated / Incomplete flags. **It returns no text from the
    input**, which is the E4 contract: it says what kind of thing it saw and how much,
    never the thing.
  - **Checks beyond the pattern:**
    - Aadhaar: Verhoeff check digit.
    - GSTIN: check character.
    - Cards: Luhn; must start with 2–6; all-same digits rejected.
    - Bank account: an account number counts only on a line that also has an IFSC code.
  - **False-positive guard (Spike 3):** an unformatted 12-digit Aadhaar or 16-digit card
    counts only with a context word within 40 characters ("aadhaar", "uid", "आधार", "card",
    "visa", "cvv", …), because order and invoice numbers look exactly like them. The
    formatted forms (4-4-4, 4-4-4-4) count on their own.
  - **Safety:**
    - Digits are ASCII only: .NET's `\d` would also match Devanagari digits.
    - Every regex has a 500 ms timeout; a timed-out scan is reported Incomplete, never
      clean.
    - Input is capped at 5M characters, and a capped scan is flagged Truncated.
    - Admin keywords are matched literally (escaped), as whole words, at most 200.
  - **Checked:** `PiiScannerTests` (14):
    - published checksum examples;
    - each kind found in ordinary text;
    - bare digit runs needing context;
    - six look-alikes not reported;
    - Devanagari digits ignored;
    - contact list against prose;
    - keyword semantics;
    - no input text in the serialised result;
    - the size cap.
  - All 323 agent tests on the `phase-3` base pass.
  - **Speed:** Spike 3 measured these patterns on one core: 10 KB in 5 ms, 1 MB in 55 ms,
    about 50 MB of memory.
  - **Not yet:** false-positive rates on real business documents (needs pilot samples), and
    wiring it into the extension and native host (D3/E4).
- **D5 Zero-config discovery:** low-priority scheduled file scan → sensitivity map by folder
  (counts only) → suggested policies for the admin to approve.
  - **As built, slice 1, the map (17 Nov, branch `phase-3`):**
    - **Switch:** "Find where sensitive files are kept" on the Browser policy page
      (`discovery_enabled`). Off until an admin turns it on; AI Guard only.
    - **Where the scan runs:** `savio-guard-host.exe --discover <folders>`, started by the
      service at idle priority. This is the process E4 keeps off the network, and E4's
      firewall rules now also apply whenever discovery is on. File contents are read only
      there.
    - **What it reads:** text-like files and Word / Excel (`.docx` / `.xlsx`, unzipped with
      the standard library), up to 20 MB each, at most 50,000 files a run.
    - **What it skips:**
      - cloud-only OneDrive placeholders (reading one would download it);
      - hidden, system and linked entries;
      - AppData, dot-folders and dependency folders;
      - a zip entry larger than its limit, by its declared size.
    - **Where it looks:** each real account's Desktop, Documents, Downloads and OneDrive
      folders, taken from the registry's ProfileList.
    - **What leaves:** one line per folder where something was found (path, files read,
      files with findings, counts per kind, contact lists). No file names, no text. The
      service checks every path lies inside a folder it asked about, and every kind is known.
    - **When:** weekly, remembered across restarts; a failed run is tried again 30 minutes
      later.
    - **Backend:** `guard_discoveries` (migration 0091), one row per PC, replaced by each
      scan. Fixed schema, unknown fields refused. Admin only, because folder paths name people.
    - **Portal:** AI Guard → Where data lives: totals, a filter by PC, and folders sorted by
      files with findings.
    - **Checked:**
      - `DiscoveryTests` (4) on a temp tree: CSV, Word and Excel found; hidden, cloud-only,
        AppData, `.git`, `node_modules` and a fake .docx skipped; no file name or text in
        the output; size cap; weekly, off when switched off, retried on failure; a path
        outside the asked folders or an unknown kind refused;
      - the built host's `--discover` run on a temp folder gave the expected JSON;
      - backend `test_guard_discovery` (3);
      - migration 0091 up/down/up with no model drift;
      - on screen with two sample PCs.
  - **As built, slice 2, suggestions (17 Nov):**
    - **Six fixed rules** in `guard_suggestions.py`, each from the org's own evidence (the
      D5 map and the last 14 days of E3 events) and its current policy:
      - leave record-only: "redact" if most findings were on AI chat sites, else "warn";
      - block personal file-sharing sites when contact lists turn up;
      - turn off private windows when the extension is forced (it does not run there);
      - turn off extension developer mode when the extension is forced;
      - add the AI chat sites to a "sites to check" list that leaves them out;
      - turn on the file check when the browser shows sensitive data.
    - **Each card says why, in numbers,** and exactly what it will change.
    - **Apply** goes through the same audited policy update as the Browser policy page, plus
      `guard.suggestion_apply`. Lists are added to, never replaced. A suggestion that no
      longer holds is refused (404) and stops showing.
    - **Dismiss** hides it for good (`guard_suggestion_dismissals`, migration 0092), audited.
    - **Admin only.** Shown at the top of "Where data lives".
    - **Checked:**
      - `test_guard_suggestions` (4): nothing seen means nothing suggested; each rule's
        evidence and wording; apply adds to the lists, bumps the version, is audited and
        clears the card; dismiss; roles;
      - migration 0092 up/down/up with no model drift;
      - on screen, "Block personal file-sharing sites" applied: policy version 4, the
        existing blocked sites kept and the new ones added.
  - **Not yet:** a live run on the VM. (PDF text: done 18 Nov, see "Redact for forms and
    files" under D7.)
- **D7 Coaching:** warn / justify / block dialogs in-page, English only (no Hindi anywhere,
  decided 17 Nov).
  - **As built (17 Nov, branch `phase-3`):**
    - **SAVIO's own prompts:** `extension/dialog.js` replaces `confirm()` / `alert()`. It
      lives in a **closed** shadow root, so the page cannot see inside, restyle it or press its
      buttons. Only real clicks and keys count. Checked in the browser: the page's own
      synthetic Escape, Enter and click did nothing.
    - **Safe by default:** the safe button has the focus, so Enter never sends. Escape
      cancels. If a page removes the prompt, the held action simply never happens.
    - **Looks:** light and dark; scrolls on a short window.
    - **New mode "justify":** to go ahead, the person picks a reason from a fixed list
      (client asked, manager approved, test data, own information, other work reason). It is
      a list, not a text box, because the event schema has no free-text field (E4) and that
      does not bend here. A scanner that could not check still only warns.
    - **The answer is recorded:** a warn or justify event is held until the person answers,
      then sent once with `outcome` (proceeded / cancelled) and the `reason` code. The rules
      are checked in the extension, the agent and the backend: a reason only when going
      ahead after justify, never otherwise.
    - **Backend and portal:**
      - migration 0089 adds `outcome` and `reason`;
      - the summary counts "went ahead anyway", "stopped" and each reason;
      - "What was found" shows them per event;
      - the browser policy page offers "Ask for a reason".
    - **Fixed on the way:** the extension's store description said nothing is sent to
      SAVIO's servers. That stopped being true with E3; it now says what is sent (kind and
      where, never the text).
    - **English only:** no Hindi anywhere in the product (decided 17 Nov). Every string sits
      in one table in `dialog.js`.
  - **Redact (17 Nov):**
    - **Mode "Hide the sensitive parts":** a paste goes in with each finding replaced by a
      label (`[PAN]`, `[Aadhaar]`, `[card number]`, `[restricted]`, …), and a small notice
      says so.
    - **How:** the scanner's `Redact()` uses exactly the checks `Scan()` uses. A bare order
      number with no context word stays as it is, in both. Kinds the policy ignores are kept.
    - **Where it applies:** only a paste could be rewritten at first; forms and text files
      followed on 18 Nov (below).
    - **When it cannot redact** (over 5M characters, or a timeout), it warns rather than
      pasting unchecked text.
    - **The redacted text** goes back only to the browser on that PC, never into an event.
  - **Redact for forms and files, and documents read (18 Nov):**
    - **Forms:** in redact mode, a form's text fields (text and search inputs, text areas) go
      ahead with findings replaced. They are set the way a page's framework expects (the
      native setter plus an input event), so a React form sends the new value too. The form's
      other values (selects, hidden, e-mail, number…) are the fixed rest. Passwords are never
      read.
    - **Text files chosen for upload:** each file with a finding is swapped for a copy, same
      name and type, with the findings replaced.
    - **The rule that keeps "hidden" honest:** what cannot be rewritten (a form's other fields,
      a Word or PDF file, pasted or dropped files) must be clean, or could-not-check counts as
      not clean. Otherwise the person is asked (warn) instead of being told it was hidden.
      A drop still always warns.
    - **Documents are read now:** Word and Excel uploads (`.docx` / `.xlsx`) go to the native
      host as base64 (`scan_file`), which reads them in memory with the same code as the
      weekly map (`Documents.cs`) and answers with counts only. Old `.doc` / `.xls`,
      PowerPoint and archives are still "could not check". Up to 5 MB a file, 20 MB a check.
    - **PDF, the admin's choice:** "Read the text inside PDFs" (`guard_read_pdfs`, off by
      default) on the policy page. It covers uploads (the extension's `readPdf`) and the
      weekly map (`--pdf`). Off: an uploaded PDF is "could not check" and the map skips PDFs.
      - Parser: **PdfPig 0.1.16** (Apache-2.0, pure .NET, no dependencies of its own; NuGet
        id `PdfPig`). Chosen because a PDF cannot be read without a parser, and this one
        brings no native code into the process that reads other people's files.
      - At most 500 pages, 10 seconds, and the scanner's character cap. Encrypted, broken,
        or slower than that: "could not check". It runs in the host, which E4 keeps off the
        network.
      - ponytail: an overrunning parse is abandoned, not stopped (PdfPig has no
        cancellation). For an upload the host process ends with the check; in the weekly
        map it can keep a core busy until the run ends. Upgrade path: one child process per
        PDF, killed at the limit.
    - **Checked:**
      - agent `DocumentsTests` (7): a real PDF made with PdfPig read only when chosen; files
        that are not what their name says, too big, or old Word are null; the host answers a
        PDF or Word upload with counts and no text, refuses broken data; the weekly map reads
        a PDF only with `--pdf`. `readPdf` reaches the extension only when on. Agent suite 447.
      - extension `background.test.mjs` (2), with a fake browser and host: each part
        redacted; a PAN in the fixed rest or in a PDF means warn; a form sent without its
        parts warns; a paste is still rewritten whole; documents read by the host; an
        unreadable one is unknown. `decide` / `mergeScans` tests. Extension suite 20.
      - backend: the switch is off by default and served to the PC.
      - in a page, in the browser pane, with the extension's APIs faked and real typing and
        clicks: the site's own submit handler received `Client PAN [PAN]` with the other
        fields untouched, and a PAN in a hidden field led to the prompt, and nothing was
        sent when it was cancelled.
    - **Not checked:** the file swap in a real browser (a file can only be chosen through the
      operating system's dialog), and the whole thing with the real host in Chrome. Both are
      the VM test.
  - **Approvals (17 Nov):**
    - **Mode "Needs IT approval":** the prompt offers "Ask IT for approval" or "Don't". A
      request is an event with `outcome: requested`. The backend turns it into a
      `guard_approvals` row (migration 0090) and notifies the admins.
    - **Deciding:** admins approve, for 15 minutes to 8 hours, or deny, under AI Guard →
      Approvals. Every decision is audited. A request unanswered for a day expires.
    - **What an approval covers:** that Windows account, that PC, that site, that channel,
      until that time. Nothing wider.
    - **How it reaches the PC:**
      - only PCs whose policy is in approve mode fetch approvals, every cycle, so no other
        PC makes an extra call;
      - the service writes them to `HKLM\SOFTWARE\SAVIO\GuardApprovals\<SID>`, a key only
        that account can read, with no inherited "Users: read";
      - a standard user cannot write there, so cannot approve themselves;
      - the host checks it, and the person tries again and goes through, recorded as
        "went ahead with IT's approval".
    - **Checked:**
      - backend `test_guard_approvals` (3): dedupe, approve and serve, audit, other PC gets
        nothing, deny, expiry, bounds, roles;
      - agent: store per account, the key's ACL, the host's site / channel / time check, and
        the worker fetching only in approve mode;
      - migration 0090 up/down/up with no model drift;
      - on screen: a request appeared under Approvals, was approved for 1 hour, and the
        PC's endpoint served it. The prompt and both notices were checked on a test page.
  - **Not yet:**
    - a live run with the real service writing HKLM and the host reading it (needs the VM);
    - redacting files and forms.
- Actions available: log, warn, justify, redact (where supported), block. Default for a new
  org: **log-only for 14 days** (the pilot mode, E8).
  - **As built, E8 (18 Nov, branch `phase-3`):**
    - **When it starts:** the pilot begins when an org first saves its browser policy, and
      lasts 14 days (`org_browser_policies.pilot_until`, migration 0093). Policies saved
      before it existed have no pilot.
    - **What it holds:** until then, the backend refuses any mode but "Record only" (409).
      This covers the policy page and the suggestions alike, so it is enforced in code, not
      only in the UI.
    - **How it ends:** by the date, or when an admin presses "End the pilot now" (audited
      `guard.pilot_end`). Nothing switches on by itself: the mode stays "Record only" until an
      admin picks one. The "Ask people before…" suggestion is held back during the pilot, and
      it is the card that greets its end, with the 14 days' numbers.
    - **Portal:** a notice above the modes gives the end date and the days left, and the other
      modes are greyed out until the pilot ends.
    - **Checked:**
      - `test_a_new_org_only_records_for_14_days`: refused before and during the pilot, agent
        served "log", ends by date with nothing switched on, ended early by an admin only,
        audited;
      - suggestions: the record-only card is hidden during the pilot;
      - migration 0093 up/down/up, with a pre-existing policy row kept and given no pilot;
      - on screen, light and dark: the notice, the greyed modes, and "End the pilot now"
        (modes enabled, audit row written).

#### 3a security review (17 Nov)
Three `security-reviewer` passes: the agent, the extension, and the backend with the portal.
Each finding was checked against the code before it was fixed.

- **Fixed: agent**
  - **C1:** the Outbound Ledger wrote the generated local-account passwords ("Temporary
    password: …") to disk. A password written into any sentence is now redacted in the ledger.
  - **H1:** a user's own `com.savio.guard` under HKCU would win over SAVIO's host.
    - `NativeMessagingUserLevelHosts=0` for Chrome and Edge.
    - Firefox has no such policy, so per-user registrations are removed from signed-in
      hives every cycle and reported as tampering.
  - **M1:** discovery re-checks every folder for a junction or symlink right before opening
    it, roots included.
  - **M2:**
    - the event pipe always keeps an instance listening, with up to 4 at once;
    - a 0.5 s read timeout;
    - a per-account limit of 60 events a minute.
  - **M3:** folder names below the root go through redaction before they leave the scanner.
  - **M4:** Firefox's `distribution\` is written to only under Program Files with no link on
    the way; otherwise the report says to use Group Policy.
  - **L1:** zip parts are read through a bounded buffer.
  - **L2:** discovery folders are passed on stdin, so there is no 32K command-line limit.
  - **L4:** the approvals parent key cannot be listed by users.
- **Fixed: backend**
  - **H1:** the "Approval requested" notification no longer names anyone. Notifications
    reach every role, while who asked for what is for admins only.
  - **M1:**
    - `windows_user` must be an account name, with no control or invisible characters;
    - report names are limited to policy-name characters;
    - tamper notifications come at most once per PC an hour;
    - reports from an org without AI Guard are dropped.
  - **M2:**
    - events older than 14 days are refused;
    - a per-PC daily cap of 5,000;
    - at most 20 open requests per PC, with retention, and pending requests listed first.
  - **M3:** a decision must quote the request's `requested_at`. A request that changed since
    the admin looked is refused, and the update matches only a still-pending row, so two
    admins cannot both win.
  - **L1:** technicians do not see restricted keywords.
  - **L2:** the policy and report bodies refuse unknown fields; keywords refuse invisible
    characters.
  - **L3:** Apply must quote the changes the admin saw; a policy made invalid is a 409; a
    double dismiss is harmless.
  - **L4:** a forced Firefox extension may come only from addons.mozilla.org.
  - **L5:** discovery `scanned_at` cannot be in the future; paths refuse invisible characters.
- **Fixed: extension**
  - **H1:** a file choice is stopped synchronously, before the site sees the files.
  - **H3:** about:blank, srcdoc and blob frames are covered, and the host comes from the
    sender's origin.
  - **M1:** listeners are on `window` in the capture phase.
  - **M2:** pasted files are checked.
  - **M3:** unreadable documents are "could not check", never clean.
  - **M4:** host names are normalized (case, trailing dot, `*.`, URL, punycode).
  - **M5:** pending events are held in the background and only an id comes back, once.
  - **M6:** only trusted events count.
  - **L1:**
    - the prompt is a top-layer `<dialog>`, so page CSS cannot hide it;
    - clicks in its first 0.4 s are ignored;
    - removing it means "no".
  - **L2:** a WeakSet replaces the DOM flag.
  - **L3:** mode changes reach open tabs.
  - **L4:** form text is read with `FormData` and re-submitted with its submitter.
  - **L6:** counts are limited to known kinds.
  - **Manifest:** the description is qualified.
- **Known limits, documented:**
  - Text a page's own script sends (fetch / XHR / WebSocket), `form.submit()`, clipboard-API
    reads, DevTools and other browsers are outside what an in-page extension sees.
  - Binary formats are "could not check", not scanned.
  - A page that opens its own modal after SAVIO's could sit above it in the top layer.
  - The Firefox per-user host is removed within a cycle, not prevented; Chrome and Edge
    refuse it by policy.
  - Discovery still runs as full SYSTEM. A restricted token is the upgrade path.
  - Chromium policy ownership is by name: a later GPO for a name SAVIO set is repaired over
    (review L3, agent).
  - The firewall rules match by name.
- **Still to check live, on the VM:** the user-level host refusal in each browser, the
  pipe under a hostile local user, junction swaps during discovery, and the firewall block.

#### 3a live test on the dev laptop (17 Nov, instead of the VM)
The phase-3 agent was installed on the dev laptop (LANCE, Windows 11, LocalSystem service, the
local backend) with the owner's go-ahead, run against real Chrome, Edge and Firefox, then
removed and the 0.15.0 agent put back.

- **Worked:**
  - **D10:** policies written to HKLM for Chrome and Edge and to Firefox's `policies.json`.
    The other tool's `LocalNetworkAccessAllowedForUrls` was left alone and never owned.
  - **Chrome honoured the policies:**
    - wetransfer.com was blocked ("Your organization doesn't allow you to view this site");
    - DevTools off refused remote debugging;
    - developer mode off stopped an unpacked extension;
    - `chrome://policy` listed the policies.
  - **Policy changes:** removed policies were removed. An empty policy removed everything
    SAVIO set: policies, 3rdparty settings, host registrations, firewall rules, approvals,
    and the Firefox keys with `savio-owned.json`.
  - **D3:** the native host was registered for Chrome and Firefox only (Edge had no
    extension ID). The installed `savio-guard-host.exe`, driven as Chrome drives it, scanned
    to counts, redacted, refused smuggled text and unknown requests.
  - **E3:** events went host → SYSTEM pipe → service → backend, attributed to `LANCE\Danish`
    by Windows. The queue file emptied after upload.
  - **Ledger:** 486 lines, no Bearer token, no device token, no unredacted password;
    SYSTEM / Administrators only.
  - **D7:** a request reached Approvals. Once approved, the host said yes for that site and
    channel only, within a cycle. The per-account key was readable by that account alone,
    and the parent key was not listable by users.
  - **H1 (security review):** fake per-user `com.savio.guard` registrations planted in the
    real hive were removed within a cycle, reported as `repaired: user-level
    com.savio.guard`, and raised a "Browser policy tampered" notification.
  - **E4:** both firewall rules were set on the host exe. The laptop's Windows Firewall is
    off on all profiles, and the report said so ("not enforced … SAVIO leaves the firewall
    setting to you").
  - **D5:** the weekly scan ran: 36 files read, 2 skipped, 2 folders with findings,
    counts only.
- **Found and fixed:** a LocalSystem service could not identify an event's sender.
  Impersonating an Identification-level client of another account failed; the unit tests ran
  as one account and could not show it.
  - The service now takes the account from the client process's own token, named by the
    kernel (`GetNamedPipeClientProcessId`).
  - The pipe now carries a length, the event and a one-byte answer, so the host knows
    whether it was taken.
- **Learned about testing from the Claude app:** registry writes made from inside it are
  virtualised (MSIX), so they reach neither the browsers nor the service. Test keys were
  planted as SYSTEM instead.
- **The extension in real Chrome (manual install):** Chrome refuses an unpacked copy of a
  force-listed ID ("blocked by the administrator"), so the policy gained `extension_install`:
  `store` (default) or `manual`. Manual writes everything except the force-install entry, needs
  developer mode, and has no Firefox install URL. With it, a keyed unpacked copy in a
  throwaway profile:
  - read its managed settings and reached the native host;
  - warn: the prompt appeared; "proceeded" and "cancelled" reached the backend;
  - justify: the reasons prompt appeared;
  - redact: "PAN [PAN], card [card number], re [restricted]" was pasted, with the notice;
  - block: the "SAVIO blocked this" dialog appeared.
- **Found and fixed in the extension test:** every guard-mode change was reported as
  tampering ("changed on this PC and put back"), which alerted the admin. The agent cannot tell
  the org's new value from someone else's. The backend now treats repairs in the first report
  of a new version as an update. It keeps each PC's last version, so this holds across agent
  restarts. A planted user-level host is still tampering.
- **Learned:** an open Chrome re-reads policy on its own 15-minute timer (seen at 17:38, 17:53
  and 18:08). With the agent's hourly fetch, a mode change reaches an open browser within about
  75 minutes. A forced Windows policy refresh (`RefreshPolicyEx`) did not shorten this, so the
  agent does not call it. `chrome://policy` → "Reload policies" applies a change at once.
- **Not covered here:**
  - the store-installed extension, which needs the store listing;
  - a host that really cannot connect, because the firewall is off on this laptop;
  - a junction swap during a scan.
- **Left on the laptop:**
  - an empty Firefox `policies.json` (`{"policies": {}}`), which has no effect;
  - the agent's admin-only `state` files from the test (ledger, `discovery-last.txt`,
    `p3test`);
  - the backup of the 0.15.0 agent, `C:\Program Files\Astra\Agent.bak-p3test` (delete as
    admin).
  - The 0.15.0 agent is running again.

### 3c — Smart Guard: what makes it more than a DLP (decided 18 Nov, before 3b)
Why: a list-and-policy DLP is what the market sells, and it drowns IT in alerts. The Cloud
Security Alliance's 2026 survey (433 IT/security people): 54% triage alerts that are mostly false
positives; 9 in 10 felt alert fatigue; only 16% of those who lost data had DLP stop the biggest
incident first. SAVIO's answer is to read the pattern, rank it, explain it, and act on it.

| Module | Definition |
|---|---|
| **C1 Cases, not alerts** | Events are joined into one case per person while they keep coming (48 h). Each case gets a severity from the whole story (how much, what kind, where to, went ahead after a warning, how many places) and the reasons in plain words. Only high-severity cases notify, once per case; the rest wait on the Cases page. IT closes a case as "expected" (optionally "stop raising cases for this site") or "handled"; quiet sites are counted, never hidden. |
| **C2 File origin** | Where an uploaded file was downloaded from: "this Excel came from your CRM". Feeds C1's severity. (Built from the browser's downloads, not Mark of the Web; see below.) |
| **C3 Smart USB** | Observe; warn after copy; read-only; company drives only (serial allowlist); encrypted only (BitLocker To Go); **write window on request** (read-only by default; a person asks, IT or the policy opens 30 minutes, everything copied is checked and logged; reuses D7 approvals); block. Per-file "block only sensitive files" needs a signed minifilter driver: later. |
| **C4 SAVIO acts** | A case offers the fix: USB off on that PC, sign the session out, disable the account, IT approval for that person, through the existing tiers and audit. |
| **C5 Adaptive strictness** | Controls tighten for one person as their cases rise (warn → approval → block); a resignation flag starts 30 days of watch. Needs the privacy review and the lawyer (with D8). |

**C1 as built (18 Nov, branch `phase-3`):**
- **Cases:** `guard_cases` + `guard_quiet_sites` (migration 0096). Every event batch updates
  each person's open case (`guard_cases.update`, called from ingest). A case stays open while
  events keep coming within 48 h; after that the next event starts a new one. A closed case is
  never reopened. Events with only ignored kinds (e-mail by default) or nothing checkable are
  not part of a story.
- **Score:** fixed code in `guard_cases.score`, explained in its docstring: how it ended (went
  ahead after a warning 3, record-only 2, blocked or asked IT 1, hidden or stopped 0.5) × where
  (personal file sharing, personal e-mail, paste sites 3; AI chat, messaging, social 2; a site
  new to the org this week 2; else 1) × (1 + items/50 + 5 for a contact list + 2 for a keyword),
  plus 5 per extra site. High ≥ 40, medium ≥ 10. The reasons are written from the same numbers
  ("350 PANs…", "to wetransfer.com (personal file sharing)", "went ahead after a warning 2
  times", "across 3 sites").
- **Noise:** only a high case notifies, once. Notifications are seen by the whole org, so the
  message names no person and no PC; the case is on the Cases page, admins only.
- **Closing:** "Handled", or "Expected (normal work)" with an optional quiet site (only a
  site in that case). A quiet site's events are still stored and shown under "What was found",
  and counted on the Cases page ("N events in 30 days, not raised"); undo is one click. All
  audited (`guard.case_close`, `guard.quiet_site_remove`).
- **Portal:** AI Guard → Cases (first in the group): open / closed, counts by level, quiet
  sites, each case with its reasons and a per-site table. Fixed on the way: "Browser policy"
  was lit in the sidebar on every AI Guard page.
- **Checked:** `test_guard_cases` (3): the score on its own (low, high, medium with a new site,
  ignored kinds, redaction, spread); one case growing to high with one notification naming no
  one, admins only; a new case after 48 h, closing rules, quiet sites kept and counted, undo,
  audit. On screen against the local backend with a made-up PC: three events from one person
  (personal mail with a contact list, WeTransfer after warnings, a blocked ChatGPT paste) became
  one high case scored 153 with those reasons; another person's two small pastes one low case,
  closed as handled from the page.
- **Not yet:** a daily digest of medium and low cases (needs the J6 alert channels); events
  older than an open case's start (an offline laptop) stay out of it.

**C2 as built (19 Nov, branch `phase-3`):** where an uploaded file came from.
- **Not Mark of the Web:** a browser never tells a page or an extension the path of a file being
  uploaded, so the file's Zone.Identifier can't be read at upload time. Instead the extension
  sees the downloads themselves (`downloads` permission): each finished download's file name,
  size and site, kept in the browser's own local storage for 30 days (at most 500). A blob: or
  data: download is credited to the page it came from.
- **Matching:** when files are uploaded, dropped or pasted, the most recent download with the
  same name and size gives the site (`originFor`). An edited file (other size) has none.
- **What leaves the browser:** the site only, as `origin` on the event, a host name checked by
  the extension, the agent's `GuardEvent`, and the backend (migration 0097). Never the file name.
- **Old and new together:** the agent sends `origin` only when it has one; the extension, if
  an agent from before C2 refuses the event, sends it again without the field.
- **Cases:** a file downloaded from another site weighs ×1.5 (the same site or one inside it
  does not count), the site's row shows "Came from", and the reasons say "files downloaded from
  crm.zoho.com". "What was found" rows carry `origin` too.
- **Checked:** extension tests (download origin for normal, blob and data downloads; the latest
  same-name-and-size match; host only; a recorded download then an upload carrying the site and
  not the name; the resend for an older agent), agent `GuardEvent` (host only, left out when
  unknown), backend (refused when not a host, stored, shown, the ×1.5 and the reason). Agent
  suite 449, extension 22.
- **Not checked:** in a real browser with real downloads. That is the VM test.
- **Mark of the Web still has a use:** in the weekly file map (D5) and for USB copies (C3),
  where the agent does see the file on disk. Done with C3.

**C3a as built (19 Nov, branch `phase-3`):** USB drives and phones by Windows' own policies.
- **Modes** (`usb_mode` on the browser policy, so per group too): off (default; SAVIO leaves
  USB alone) · read-only · encrypted drives only · read-only with IT write windows · block.
- **How:** the Removable Storage Access policies and BitLocker's, names and values read from the
  ADMX templates on this laptop (RemovableStorage.admx, VolumeEncryption.admx):
  - read-only: `Deny_Write` = 1 under `HKLM\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices\`
    for removable disks `{53f5630d-…}` and the two phone/camera (WPD) classes `{6AC27878-…}`,
    `{F33FDC04-…}`;
  - block: `Deny_All` = 1 there;
  - encrypted only: `RDVDenyWriteAccess` = 1 under
    `HKLM\SYSTEM\CurrentControlSet\Policies\Microsoft\FVE` (BitLocker To Go), phones read-only.
- **Writer:** the same owned-names writer as the browsers, reported as "Usb" and
  "UsbEncryption": an org's own GPO for any of these is a conflict, never overwritten; a key
  SAVIO has never used is not even created.
- **Write windows:** in "read-only, IT can allow writing" mode, an admin opens a window for one
  PC (15 minutes to 8 hours) from the PC list, or ends it early; audited
  (`guard.usb_window_open` / `_close`, migration 0098). Only PCs in that mode ask for it, every
  cycle, so it arrives within a minute. The PC keeps the end time and puts read-only back by
  itself, online or not; the values go and come back as "removed" / "set", never as tampering.
  A window is not served once the PC's policy leaves that mode.
- **Checked:** agent tests (each mode's values, inside and outside a window, nothing created when
  unused, the window going and coming back without a tamper flag, a GPO's value left alone; the
  worker asking only in that mode, keeping the last end when the backend is unreachable, closing
  early); backend `test_usb_modes_and_write_windows` (validation, 409 outside the mode, bounds,
  roles, served to that PC only, PC list, not served after the mode changes, audit). Agent suite
  451. On screen against the local backend: the mode saved as version 19, a window opened on a
  made-up PC ("USB writing allowed until 2:54 AM") and ended early.
- **Not checked:** Windows honouring these on a real drive, and whether a drive already plugged
  in needs reconnecting. That is the VM test.
- **C3b next:** observe what is copied to a drive (counts only, scanned by the host) as case
  events; a person asking for a window from the tray; company drives by serial number.

**C3b, part 1 as built (19 Nov, branch `phase-3`):** what is copied onto USB drives.
- **Switch:** `usb_observe` ("Record what is copied onto USB drives"), off by default, separate
  from the USB mode.
- **Agent:** `UsbCopyWatcher` lists removable drives every 3 s and watches each one. A file is
  checked once it has been quiet for 5 s (the copy is done), in batches of up to 200, by the
  native host's new `--scan` mode: the process E4 keeps off the network (its firewall rule now
  also applies when only this switch is on). The host reads text, Word, Excel and (if chosen)
  PDF, counts old Office, archives and unread PDFs as "could not check", skips photos and
  programs, and returns one total. No names, paths or text leave it.
- **Event:** one per batch, in the same fixed schema as the browser's: site and channel "usb",
  counts, contact-list flag, keyword hits, "could not check". Credited to the person signed in
  at the console. Only the service can make one: the pipe the browser side uses refuses
  channel "usb".
- **Cases:** a copy to a USB drive weighs like personal file sharing (3) and reads "copied to a
  USB drive"; the Cases table names it "USB drive".
- ponytail: the console user, not the copying process's owner (an RDP session's copy is
  credited to whoever is at the console); upgrade path is the writer's token from an ETW file
  trace. It sees after the fact; stopping is the USB mode's job.
- **Checked:** agent `UsbCopyWatcherTests` (the host's scan on real files: totals, contact list,
  keyword, the archive as could-not-check, the photo skipped, nothing named; settling and
  batching; nothing recorded when clean, signed out or switched off) and the pipe refusing
  "usb"; backend (taken, joins the case, weight and wording). Agent suite 454.
- **Not checked:** a real pen drive. That is the VM test.
- **Next in C3b:** a person asking for a write window from the tray; company drives by serial.

**C3b, part 2 as built (19 Nov, branch `phase-3`):** company drives only.
- **Use case:** the company buys a few drives (Tally backups, files for the CA, a client
  presentation) and only those work; a personal pendrive does not; a lost company drive is
  removed from the list. The write window stays for one-off needs.
- **Mode:** `usb_mode` "company_drives", with `usb_approved_drives` ({id, name}, at most 100) in
  the policy itself, so approving or removing a drive is a new version (never mistaken for
  tampering) and a group can have its own list. Phones are read-only in this mode.
- **How (no driver):** Windows' Device Installation Restrictions (DeviceInstallation.admx, read
  on this laptop) under `HKLM\SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions`:
  `AllowDenyLayered` = 1 (Windows 10 21H2+), `DenyDeviceIDs` = 1 with list `USBSTOR\Disk`,
  `DenyDeviceIDsRetroactive` = 1 (a personal drive used before stops working too), and
  `AllowInstanceIDs` = 1 with the approved drives' exact instance IDs. `USBSTOR\Disk` is the
  compatible ID of USB mass-storage disks only: this laptop's own NVMe disk is `SCSI\Disk`
  (checked), so internal disks, keyboards, mice and phones are never caught. The disk *class*
  was deliberately not used: it would include internal disks.
- **Writer:** one policy, all or nothing (as for Microsoft 365 on the PC): anything else under
  Restrictions (Intune, a GPO) means SAVIO writes none of it and reports a conflict. Rewritten
  when it drifts (repair), removed with its empty keys when the mode changes, untouched if never
  used. Reported as "UsbDevices" ("Company drives").
- **Drives seen:** the agent reads the USB disks Windows has installed
  (`Enum\USBSTOR\Disk&…\<instance>`: ID, name, and whether the serial is the drive's own; Windows
  makes one up, "7&…&0", for drives without one, and that one changes with the USB port), up to
  50, and sends them with the policy report when they change, only while AI Guard is on
  (migration 0099 keeps them per PC). `GET /guard/drives` lists them for admins with the PCs
  they were seen on and the policies that approve them.
- **Portal:** "Company drives only" in the USB setting opens the approved list (remove) and
  "Drives seen on your PCs" (name it, Approve; saved with the policy). Warns when none is
  approved ("no USB drive will work") and on drives with no serial of their own.
- **Checked:** agent tests (the values written, `USBSTOR\Disk` only, idempotent, repair, no empty
  allow list, removal with empty keys, someone else's restrictions left alone, drives read from a
  sandbox Enum with the made-up-serial flag, CD drives skipped, IDs validated; the worker sending
  drives on change and only while on); backend `test_company_drives` (reports, an internal disk
  refused, names cleaned, admins only, approval as a new version with dedupe, served, approved
  where, bad names and IDs refused). Agent suite 457. On screen against the local backend: a
  made-up PC's two drives listed (one flagged "no serial of its own"), one approved as "Accounts
  drive 1" and saved as version 20; the local policy then set back to off (version 21).
- **Not checked:** Windows actually refusing an unapproved drive and accepting the approved one,
  and the retroactive removal. That is the VM test, with two real pendrives.
- **Next in C3b:** a person asking for a write window from the tray.

**C3b, part 3 as built (19 Nov, branch `phase-3`):** asking IT for USB writing from the tray.
- **Tray:** "Ask IT to allow USB writing…" appears only on a PC whose policy is "read-only, IT can
  allow writing" (the tray asks the service each time the menu opens); while a window is open it
  reads "USB writing allowed until 14:30". The person picks a reason from a fixed list (files for
  a client, CA or auditor · a company backup · a presentation or meeting · another work reason),
  never typed text, and gets a balloon saying whether it was sent.
- **Service:** a new local pipe, `SAVIO.UsbRequest`, with two requests (`status`,
  `request:<reason>`), the same rules as Fix-my-internet (SYSTEM-owned, signed-in people only,
  no network; the tray refuses a pipe not owned by SYSTEM). Who asks is read from the client
  process's own token, as for the browser's events, never from the message.
- **Backend:** `POST /agent/usb-request` (409 unless the PC's own policy is on_request). It is an
  approval request with channel "usb" and the reason code (migration 0100), in the same queue,
  limits and notification ("…approve USB writing on their PC", naming nobody). Approving it for N
  minutes opens that PC's write window until then; it is not served to the browser's host as a
  site approval.
- **Portal:** Approvals shows "wants to copy files onto USB drives · Reason: …"; "What was found"
  now names the "usb" channel ("Copied to USB"), which part 1 had left unlabelled.
- **Checked:** agent `UsbRequestPipeTests` (status per mode and window; a listed reason only; the
  person from Windows over a real pipe; nothing sent outside the mode, while open, or without a
  person; unreachable backend), tray builds; backend `test_usb_requests_from_the_tray` (409
  outside the mode, bad reason / account / extra field refused, asked twice is one request,
  reason shown, notification naming nobody, approving opens the window, not a site approval).
  Agent suite 460. On screen against the local backend: a made-up PC in a group whose own policy
  is "write on request" asked (reason: a presentation); the request showed on Approvals with its
  reason and was approved for 30 minutes.
- **Not checked:** the tray menu and dialog on a real desktop with the real service. That is the
  VM test.

**C4 as built (19 Nov, branch `phase-3`):** SAVIO acts on a case.
- **What it offers,** per PC the case happened on (`GET /guard/cases/{id}/actions`, admin):
  block USB storage there; tell the person to stop (a message on their screen, text editable);
  lock their screen; sign them out (unsaved work lost, said in the label); disable their
  account on that PC. All existing remediation actions, nothing new on the agent.
- **Only what can be done now:** the session actions need the person signed in on that PC
  (their session ID from the PC's own session list), else "ravi is not signed in on CASE-DEMO
  now"; disabling is offered only for a local account (DOMAIN = the PC's name), else "a domain
  or Microsoft account: disable it in Active Directory or Entra"; USB block not if already
  blocked.
- **Through the existing tiers:** the portal runs each with the ordinary remediation endpoint,
  the admin clicking being the approver, after a confirm step; tier rules, audit and the
  Remediation page apply unchanged. The task's reason names the case ("AI Guard case: 300
  PANs to wetransfer.com"). The AI is never handed these: they are an admin's choice on a
  case (lock and message stay operator-only).
- **Checked:** `test_a_case_offers_fixes_through_the_existing_tiers` (the five actions; lock not
  offered until the person is signed in, then with their session ID; the default message;
  admins only; one run through `/remediations` with approve; a domain account's disable refused
  with the reason). On screen against the local backend: the made-up CASE-DEMO case listed
  "Block USB storage on CASE-DEMO" and "Disable ravi's account", the session actions marked
  "not signed in", and the USB block sent after the confirm step.
- **Not checked:** the actions running on a real PC from a case (each action itself is already
  covered by its own tests). That is the VM test.

**S1 as built (19 Nov, branch `phase-3`):** SAVIO names sites the fixed list does not know.
- **When:** after a batch of events arrives, off the response path (`guard_sites.classify_new_sites`,
  a background task like Tracker's), the org's sites from the last 30 days that the fixed list
  does not cover go to the AI, at most a dozen a pass, by registrable domain (one answer covers
  every subdomain). USB and intranet names are never asked about. No AI key: nothing happens.
- **Kept once, for everyone:** in Tracker's global `learned_categories` store with kind "guard";
  no new table. A site is asked about once, ever.
- **What the model may say:** one key from a fixed list (the six site categories, "business"
  for a work tool, "other"). It sees host names only, never content, counts or people; the
  system prompt says host names are data, not instructions; an answer for a host it was not
  asked about, or a key not on the list, is dropped. A hostile host name can at worst be filed
  under the wrong kind.
- **Cases:** the fixed list first, then the AI's kind. A risky one weighs as its kind, and the
  reason says "(personal file sharing, recognised by SAVIO)"; a business tool or "other" weighs 1
  and is not counted as new.
- **Suggestion:** "Block N risky sites SAVIO found": AI-recognised personal file sharing, personal
  e-mail or paste sites that sensitive data went to in 14 days and that no list blocks; Apply adds
  them to the blocked sites (audited, a new version). Keyed by the set of sites, so a site found
  later brings a new card even after one was dismissed.
- **Checked:** `test_guard_sites` (only unknown internet sites asked about, the list first, a
  hostile-looking name treated as a name; the case reason and weights; with a stand-in model: no
  key no call, two learned, an unasked host and an off-list key dropped, asked once only, the
  listed site never sent; the suggestion's wording and change, applied, then gone).
- **Not checked:** the real model's answers (no AI key locally, by design: no production secrets
  on this laptop). Worth a look on staging with a few real sites.

S1–S5 (AI site intelligence, pattern suggestions, productivity suggestions with Tracker,
learning from the admin, weekly brief) fold into C1–C4 as they are built: C1's site weighting
is where S1's AI site categories plug in.

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
| 1 | Done: merged to main (PR #57) |
| 2 | Built on branch `phase-2`, draft PR #63. Left: vendor warranty connectors (needs API access), invoice → AI, scheduled e-mails/alerts (waits for a scheduler), and the live checks (BitLocker escrow, Defender tamper, L3 model) |
| 3 | Not started (spikes first) |
| 4 | Not started |
| 5 | Not started |
