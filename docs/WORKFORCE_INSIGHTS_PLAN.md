# ASTRA — Workforce Insights (Time & Productivity Tracking) — Plan & Cost

A new ASTRA module: per-user work-hours, breaks, active/idle time, and app/website
productivity — built on the agent that is already on every endpoint. This document is the
full plan: scope, architecture, the **configuration/category system**, the **per-user cost**,
and the phased build. Costs follow the same assumptions as
[COST_MODEL_2K_DEVICES.md](COST_MODEL_2K_DEVICES.md): monthly, USD with **₹88 = $1**, vendor
list prices ex-GST. Figures marked *estimate* are engineering estimates, not invoices.

> **This is employee monitoring.** It ships transparent-only (the Tray shows tracking is on),
> entitlement-gated, RBAC-scoped, and audited. Red lines: **no keystroke logging, no
> screenshots, no query-strings, nothing covert.** See §6.

---

## 1. Scope (agreed 2026-10-15)

| Decision | Final |
|---|---|
| Purpose | Attendance **and** productivity |
| Depth | Session events + idle/active + foreground app/website |
| Website capture | **Path without query** (`?…` stripped), per-org opt-in + attestation, sensitive-domain exclusion; default is domain-only |
| Visibility (RBAC) | Org admin = all · team manager = own team · employee = self-view |
| Consent | Transparent only — Tray shows "Activity tracking: ON" |
| Gating | New entitlement `workforce_insights`, default OFF |
| Rollout | Phased: P1 attendance → P2 idle → P3 app/website |

---

## 2. Architecture

### 2.1 Agent (new collectors — all batched, pushed with the existing 60 s telemetry upload)

Reusing the existing push means **no new requests/min per device** — the agent already uploads
telemetry every 60 s; activity rides along in the same body.

- **Session events** — logon / logoff / lock / unlock. Mostly already available (WTS
  `SessionEntry` + Security event log 4624/4634/4800/4801).
- **Idle detection** — `GetLastInputInfo` (keyboard/mouse). No input ≥ threshold ⇒ idle/break.
- **Foreground app + website** — active window process + title; browser URL via **UI
  Automation** reading the address bar (no extension). Runs in the **Tray** (user session), not
  the LocalSystem service — the service cannot read a user's foreground window, and this is
  exactly what ASTRA's `user` vs `system` execution split is for.
- **Transparency** — Tray shows "Activity tracking: ON" with a "what's collected" link.

**Capture caveats (honest):** only the *active* tab's URL is readable; sampling is polling-based
(~30 s), so sub-sample visits are missed; incognito/hardened browsers may hide the address bar.
Good enough for time tracking, not forensic.

### 2.2 Backend (FastAPI, reusing the telemetry pipeline)

- New telemetry type `activity` on the existing ingest path (Pydantic-validated, NUL-stripped,
  rate-limited — same as other telemetry).
- Tables (Alembic): `activity_samples` (raw, retention-limited) → `work_sessions` (derived
  work/break spans) → `daily_user_summary` (per-user-per-day rollup: first-in, last-out,
  worked, active, idle, productive/neutral/unproductive minutes).
- Aggregation service turns raw samples into sessions + daily summaries (nightly + on-demand).
- **Category policy** resolution (see §3).
- Gating: `workforce_insights` entitlement, default OFF, toggled per org by platform admin —
  same pattern as remote control (entitlement + per-org enable, audited).

### 2.3 Portal (Next.js)

- **Attendance** (P1): per-user day/week/month — first-in, last-out, worked hours, break gaps,
  late/overtime vs shift; export CSV (into the existing reporting module).
- **Activity** (P2): active-vs-idle split, break timeline.
- **Productivity** (P3): productive/neutral/unproductive split, top apps/sites, team dashboard.
- **Configuration** (§3): category rules, shifts, idle threshold, exclusions, exemptions.
- RBAC everywhere: admin = all, team manager = own team, employee = self. Access to the
  sensitive views is itself audited.

---

## 3. Configuration & category system (admin-facing)

The product ships with a **sensible default classification so it works out of the box**, and the
admin reclassifies anything to fit their business.

### 3.1 Built-in default taxonomy

Three buckets: **Productive · Neutral · Unproductive**. Starter mapping (editable):

| Category | Default bucket | Examples (apps / domains) |
|---|---|---|
| Development | Productive | VS Code, Visual Studio, JetBrains, terminal, github.com, gitlab.com, stackoverflow.com |
| Office / docs | Productive | Word, Excel, PowerPoint, docs.google.com, sheets, Adobe Acrobat |
| Design | Productive | Figma, Adobe XD/PS/AI, Canva |
| Work communication | Productive | Teams, Slack, Zoom, Google Meet, Outlook, Gmail (work) |
| Project / ticketing | Productive | Jira, Linear, Asana, Trello, Notion, ClickUp, Monday |
| CRM / ERP / finance | Productive | Salesforce, HubSpot, Zoho, SAP, Tally, QuickBooks |
| Cloud / admin consoles | Productive | AWS, GCP, Azure, Vercel, internal dashboards |
| Search / reference | Neutral | Google search, Bing, Wikipedia, AI assistants |
| System / file / email (generic) | Neutral | Explorer, Settings, generic browsing, unknown apps |
| News | Neutral | news sites (org can move to either bucket) |
| Social media | Unproductive | facebook, instagram, x/twitter, reddit, tiktok, snapchat |
| Streaming / entertainment | Unproductive | youtube, netflix, prime video, spotify, hotstar |
| Gaming | Unproductive | Steam, Epic, game clients |
| Shopping | Unproductive | amazon, flipkart, myntra |
| Gambling / dating | Unproductive | (blocked-leaning) |

Context matters — YouTube is a tutorial for a developer and a time-sink for someone else — so
**every row is overridable**, globally, per-org, and per-team.

### 3.2 Admin configuration options (portal)

- **Reclassify** any app/domain → Productive / Neutral / Unproductive; create **custom
  categories**.
- **Rule types**, most-specific-wins: exact process name · app display name · website domain ·
  domain + path prefix.
- **Per-team overrides** — a domain can be Productive for Sales and Neutral for Engineering.
- **Working hours / shift** per org or per team — drives late / early-leave / overtime and
  scopes tracking to work hours.
- **Idle threshold** — default 5 min no-input = break (configurable).
- **Sensitive-domain exclusion list** — banking / health / gov: never store the path, only a
  "private site" placeholder.
- **Exemptions** — per-user or per-role (e.g. execs) excluded from tracking.
- **URL mode** — domain-only (default) or path-without-query (opt-in + attestation).
- **Retention** — raw samples (default 90 d) and aggregates (default 1 yr).
- **Bulk import/export** of category rules (CSV) to seed quickly.

### 3.3 Resolution precedence

`team rule  >  org rule  >  global default  >  uncategorized (Neutral)`

Resolved on read and shown in the UI, so a surprising classification is always traceable to the
exact rule that produced it.

---

## 4. Per-user cost

### 4.1 Assumptions

- Tracked user: ~8 work-hours/day × 22 days/month.
- Activity stored as focus-change + idle-transition events plus periodic samples ≈ **600
  rows/day/user**; ~0.35 KB effective per row with indexes.
- Pushed inside the existing 60 s telemetry upload ⇒ **no extra requests/min per device**.
- Raw retention 90 days; daily summaries kept 1 year.

### 4.2 Incremental cloud cost per tracked user / month *(estimate)*

| Component | Basis | $/user/mo | ₹/user/mo |
|---|---|---|---|
| DB storage | ~15–20 MB retained @ ~$0.35/GB-mo | ~$0.01 | ~₹1 |
| DB compute | +~40% write volume for tracked users + nightly aggregation + dashboard reads | $0.05–0.12 | ₹4–11 |
| API / ingest (Cloud Run) | batched into existing push; aggregation job | $0.01–0.03 | ₹1–3 |
| Egress | dashboard + export traffic | ~$0.01 | ~₹1 |
| **Incremental infra total** | | **$0.08–0.18** | **₹7–16** |

**Headline: ≈ ₹10–15 per tracked user / month** of incremental cloud cost at a few-thousand-user
scale. This *drops* with committed-use discounts as volume grows, and is a rounding error next
to ASTRA's existing ~$0.65/device/mo baseline.

### 4.3 At scale *(incremental, on top of baseline infra)*

| Tracked users | Extra infra / month |
|---|---|
| 500 | ~$40–90 (₹3.5k–8k) |
| 2,000 | ~$160–360 (₹14k–32k) |
| 10,000 | ~$800–1,800 (₹0.7L–1.6L) |

### 4.4 One-time build cost *(estimate)*

| Phase | Work | Engineer-time |
|---|---|---|
| P1 — Attendance | migration + models + aggregation + entitlement + portal + agent idle-signal | ~2–3 weeks |
| P2 — Active/idle | `GetLastInputInfo` collector + active/idle rollups + UI | ~1–2 weeks |
| P3 — App/website | UIA capture + category engine + config UI + dashboards | ~4–6 weeks |
| | + QA + mandatory security review | included |
| **Total** | | **~2.5–3.5 engineer-months ≈ ₹5–7 lakh** |

### 4.5 Cost vs price (why this is worth building)

Comparable tools — Hubstaff, Time Doctor, Timechamp — charge customers **$4–10/user/month
(₹350–880)**. Incremental cost is **~₹10–15/user/month**. As an add-on entitlement this is
strongly margin-positive; infra cost is not the deciding factor — the legal/consent design
(§6) is.

---

## 5. Phased delivery

- **Phase 1 — Attendance** *(ship first)*: reuses existing session telemetry + heartbeat; adds
  `work_sessions` + `daily_user_summary`, the `workforce_insights` entitlement, the Attendance
  page + export, and a small Tray idle-signal. Low privacy weight, fast, immediately useful.
- **Phase 2 — Active vs idle**: `GetLastInputInfo` collector → real at-keyboard time, auto-break.
- **Phase 3 — App/website productivity**: foreground app + browser path (UIA), category engine,
  configuration UI, productivity dashboards; per-org opt-in path-without-query mode with all §6
  mitigations.

Each phase is independently shippable and testable.

---

## 6. Privacy, legal & consent (non-negotiable)

Employee monitoring. Mitigations are part of the build, not an afterthought:

- **Transparent only** — Tray shows tracking is on; no covert mode. Covert monitoring is illegal
  in several jurisdictions.
- **Path without query** — query strings/fragments stripped (that is where tokens, password-reset
  links, and health/financial parameters live). Sensitive domains (banking/health/gov) recorded
  as a placeholder, never a path.
- **Proportionality** — default domain-only; path-level is an explicit per-org opt-in where the
  customer attests they have given notice and completed a DPIA. Burden on the controller,
  documented + audited.
- **Jurisdiction notes (not legal advice — customer's counsel/DPIA required):** EU/UK GDPR needs
  a legitimate-interest basis + DPIA + proportionality (works-council consult in Germany); India
  DPDP needs notice + legitimate purpose; several US states (NY, CT, DE) require written notice,
  and full URLs raise a wiretap "contents" argument. ASTRA is a *processor* — this data
  aggregated across orgs raises breach blast-radius, so retention is short and access audited.
- **RBAC + audit** — admin/manager/self scoping; viewing the sensitive data is itself audited.
- **Red lines** — no keystroke logging, no screenshots, no screen recording, no query-strings.

---

## 7. Open decisions

- Entitlement name: `workforce_insights` (proposed) vs `time_tracking`.
- "Team manager" link: add a manager assignment on the existing team model (teams already exist:
  `team_id`, `UserTeamRead`, `TeamMembershipWrite`).
- Exact default idle threshold (proposed 5 min) and raw retention (proposed 90 d).
- Whether P1 ships before or alongside the design/DPIA note for customer legal sign-off.
