# Security Incident & Breach Notification Policy

**Technomate IT-Solution Private Limited** (CIN U62099UW2026PTC257827) · ASTRA platform
Version 1.0 · Effective 2026-09-26 · Owner: Incident Lead (below) · Review: yearly, and
after every Severity 1 or 2 incident.

The [Data Processing Agreement](https://technomateai.com/dpa/) and the [Privacy
Policy](https://technomateai.com/privacy/) promise customers a breach notice within 72
hours. This document is how that promise is kept. Drafted in-house from how ASTRA is
actually built; not reviewed by a lawyer.

---

## 1. Why this product needs its own policy

ASTRA is not ordinary SaaS. Three things raise the stakes of an incident and shape every
step below:

1. **The agent runs as LocalSystem on customer machines and executes actions.** A
   compromise that reaches the action channel is an incident on the customer's fleet, not
   only on ours.
2. **Remote support opens a live view of a person's screen.** A leaked viewer link or
   relay key is a credential to other people's desktops.
3. **Signed auto-update reaches every device.** The update signing key is held only in CI
   (`AGENT_UPDATE_SIGNING_KEY`), never on the backend — protecting it is the single most
   important control in this document.

## 2. Scope and definitions

Applies to all ASTRA systems — backend (Cloud Run, `asia-southeast1`), database (Neon,
Singapore), portal (Vercel), marketing site (Hostinger), remote-support relay (GCE
`astra-relay`, `asia-southeast1-a`), the Windows agent and its release pipeline (GitHub
Actions) — and to every employee and contractor.

- **Security event** — anything that might affect security (an alert, an odd log line, a
  report). Most are not incidents.
- **Security incident** — a confirmed or reasonably suspected compromise of the
  confidentiality, integrity or availability of ASTRA or of data it holds.
- **Personal data breach** — an incident that leads to unauthorised processing,
  disclosure, alteration, loss of access to or destruction of personal data (Digital
  Personal Data Protection Act, 2023).

## 3. Roles

A small team means one person may hold several roles. What matters is that each is
named at the start of an incident and written in the incident log.

| Role | Who (default) | Responsibility |
|---|---|---|
| **Incident Lead** | Danish — danish@technomateai.com, +91 97115 31786 | Declares severity, directs response, decides on notifications, owns the log |
| **Technical responder** | On-call engineer (Incident Lead until a second engineer is hired) | Containment, investigation, evidence, recovery |
| **Communications / Grievance** | Adeel Ahamad, Grievance Officer — grievance@technomateai.com | Customer, regulator and data-principal notices |
| **Deputy** | [Name — assign] | Takes over if the Incident Lead is unreachable for 1 hour |

Intake channels: **security@technomateai.com** (also published in
`/.well-known/security.txt`), support@technomateai.com, internal alerts (Cloud Run,
GitHub), and customer reports. Anyone who notices a possible incident reports it
**immediately** — not after investigating it themselves.

## 4. Severity

| Severity | Examples | Response starts | Update cadence |
|---|---|---|---|
| **S1 — Critical** | Update signing key exposed; agent executing an action nobody approved; cross-tenant data access; relay key / viewer links leaked; confirmed exfiltration of customer data | Immediately, 24×7 | Every 2 hours |
| **S2 — High** | Backend or database credential leaked; admin account takeover; personal data exposed to one wrong party; remote session started without consent | Within 1 hour | Every 4 hours |
| **S3 — Medium** | Vulnerability report with no evidence of exploitation; failed intrusion attempts; single-device agent tampering | Within 1 business day | Daily |
| **S4 — Low** | Policy deviation, misconfiguration caught before exposure | Within 3 business days | On closure |

When in doubt, grade higher and downgrade later. Anything involving personal data is at
least S2 until shown otherwise.

## 5. Response procedure

### 5.1 Detect and triage (T0)

1. Open an incident log (a dated file in the private incident folder) — time of report,
   reporter, what was seen. Record everything with UTC and IST timestamps from here on.
2. Assign roles and severity (sections 3–4).
3. **Start the clocks** in section 6 from the moment the incident is *confirmed* (CERT-In:
   from the moment it is *noticed*).

### 5.2 Contain

Pick the levers that fit; each is designed to be pulled without a deploy.

| Threat | Lever |
|---|---|
| AI or automation acting wrongly | Turn **automatic approval off** for each affected org (portal kill switch — there is no single platform-wide switch yet, so for a fleet-wide problem work through every org); volume limits already suspend automatic approval on unusual bursts |
| Remote support abused or relay compromised | Operator console → **disable remote control** for the org (entitlement off; agents uninstall the relay service on their next 10-minute check); for a relay compromise, stop `meshcentral.service` on `astra-relay` |
| Viewer links / relay cookie key leaked | **Rotate the relay cookie key** in Secret Manager and on the relay — this invalidates every link already issued — then redeploy the backend (the deploy names the MESHCENTRAL secrets; attaching them by hand is lost on the next push) |
| User or admin account compromised | Disable the user; revoke their refresh tokens (reuse detection already kills a stolen chain); force password reset |
| Backend secret leaked (DB URL, API keys, JWT secret) | Rotate in Secret Manager and redeploy; rotating the JWT secret signs everyone out |
| Agent/device credential leaked | Remove the device in the portal (revokes its token); re-enrol from a clean install |
| **Update signing key exposed (S1)** | Revoke the GitHub secret immediately; stop all agent releases; ship a new public key only through a *fresh installer*, since agents trust the key built into them — plan this with every customer |
| Malicious code in the repo or CI | Freeze `main`, revoke GitHub tokens and deploy credentials, review recent commits and workflow runs |

Preserve before you destroy: snapshot logs, the audit trail, Cloud Run revisions and
relevant database rows **before** rotating or deleting, where that does not prolong the
exposure.

### 5.3 Investigate

Establish: what happened, when it started, how it got in, which organisations, devices
and people are affected, what data, and whether it is still happening. Primary sources:
the ASTRA audit log (every mutation, every agent command, every remote session request and
answer), Cloud Run and Neon logs, GitHub audit log, relay logs.

### 5.4 Eradicate and recover

Remove the cause, patch, restore from known-good state, and verify — including that the
fix holds across a redeploy. Re-enable any lever pulled in 5.2 deliberately, one at a
time, and record who re-enabled it.

### 5.5 Close

The Incident Lead closes the incident when containment is verified and all notices in
section 6 are sent. A post-incident review follows within **10 business days** for S1/S2
(section 8).

## 6. Notification

| To whom | When | Trigger | How |
|---|---|---|---|
| **CERT-In** (incident@cert-in.org.in) | **Within 6 hours of noticing** | Any incident type listed in the CERT-In Directions of 28 April 2022 — includes compromise of systems, unauthorised access, data breach, data leak, attacks on servers and databases | Email in CERT-In's reporting format; keep the acknowledgement |
| **Affected customers** | Without undue delay, and **within 72 hours** of confirmation | Any personal data breach or incident affecting their data or devices (DPA §8) | Email to the org's admin contacts, followed by updates at the section 4 cadence |
| **Data Protection Board of India** | Without delay; detailed report within **72 hours** of becoming aware | Personal data breach where Technomate is the Data Fiduciary (website, account and billing data) | Board's prescribed form |
| **Affected individuals** | Without delay | Personal data breach where Technomate is the Data Fiduciary | Email, plain language: what happened, likely consequences, what we did, what they can do, contact |
| **Model provider / other sub-processor** | As needed | Incident involving their service | Their security contact |
| **Insurers** | Per policy terms (often 48–72 hours) | Any S1/S2 | Broker |

Where Technomate is a **Data Processor** (customer device and employee data), the
**customer** is the Data Fiduciary and decides on notifying the Board and individuals.
Our duty is to tell them fast and give them what they need to do so.

A customer notice contains: what happened and when; the categories and approximate number
of records, devices and people affected; likely consequences; what we have done and will
do; what they should do; and a named contact. Say what is not yet known rather than
guessing — send an initial notice on time and follow it up.

Only the Incident Lead or Communications role sends external notices. Nobody else
comments publicly or on social media about an incident.

## 7. Evidence and records

- Keep the incident log, evidence and all notices for **at least 5 years**.
- CERT-In requires ICT system logs to be kept for **180 days, within India**, and produced
  on request. ASTRA's production logs are currently in Singapore — **open action: set up
  an India-region log sink** before this is relied on.
- Every incident, including S4, is recorded in the incident register (date, severity,
  summary, affected customers, notices sent, closure date).

## 8. Post-incident review

Blameless, written, within 10 business days for S1/S2: timeline, root cause, what went
well, what did not, and actions with owners and dates. Actions go into the normal backlog
and are tracked to done. Update this policy if the incident showed a gap in it.

## 9. Prevention (standing controls this policy relies on)

- Approval tiers enforced in backend code; agent executes only allowlisted action IDs.
- Remote support: per-session consent, not recorded, file transfer and terminal disabled,
  per-org scoped relay account, AI cannot request sessions.
- Update signing key only in CI; agents verify signatures against a built-in key.
- Short-lived JWTs, rotating refresh tokens with reuse detection, RBAC, per-org isolation.
- Secrets only in Secret Manager / CI secrets; never committed.
- Audit log for every mutation and agent command; raw telemetry deleted after 7 days.
- Annual penetration test; dependency and code scanning in CI (`security` workflow).

## 10. Testing

Run a tabletop exercise at least **once a year**, rotating scenarios: signing-key
exposure, remote support abuse, cross-tenant data access, leaked database credential.
Check that every lever in 5.2 still works and that contact details in section 3 are
current.
