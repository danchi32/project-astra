# Record of Processing — SAVIO

**Owner:** Technomate IT-Solution Private Limited · **Status:** DRAFT for founder review (Z3) ·
**Drafted:** 11 Nov 2026 from the code and production settings as they are today, not from the
published policies. Where the two disagree, section 6 says so.

This is our internal map of every kind of personal data SAVIO touches: why, on what basis,
in which role, where it sits, who else gets it, how long it stays, and who can see it. It is
what we hand a customer's auditor or the Data Protection Board when asked "show us".

Update it in the same change as any feature that collects, stores or shares a new kind of
personal data.

---

## 1. Our two roles

| We are… | For… |
|---|---|
| **Data Processor** (customer is the Data Fiduciary) | Everything about a customer's staff and devices: portal users they create, device inventory and telemetry, signed-in usernames, Tracker data, AI chats, assets, remediations, remote sessions, the organisation's audit log |
| **Data Fiduciary** | Our own relationships: the customer's account administrator and billing contacts, sign-up, website visitors, leads, and our own operational logs |

Lawful basis shorthand used below:
- **Customer's instruction**: we process as their processor under the contract and DPA. The customer relies on its own basis, usually legitimate use for employment or IT security under DPDP s.7.
- **Contract**: necessary to provide the service the account holder signed up for.
- **Legal obligation**: tax, company law, CERT-In.
- **Consent**: given by the individual, withdrawable.

---

## 2. Where data lives

| System | Provider | Location | Holds |
|---|---|---|---|
| Product API | Google Cloud Run (`astra-backend`) | Singapore (asia-southeast1) | Data in transit and in memory only |
| Product database | Neon PostgreSQL | Singapore (ap-southeast-1) | All product data at rest |
| Remote-support relay | MeshCentral on Google Compute Engine, run by us | Singapore (asia-southeast1) | Live session stream in transit; relay's own logs on the VM |
| Operational logs | Google Cloud Logging `_Default` | `global`, 30 days | Request logs (URL, IP, user agent), app output |
| Operational logs (copy) | Google Cloud Logging `india-logs` (Z1) | **India (asia-south1)**, 400 days | Same as above |
| Web portal | Vercel | Global edge | Application code only; no data at rest |
| Marketing service | Cloud Run (`astra-marketing`) + its own PostgreSQL | Singapore | Leads, submissions, content drafts |
| Marketing website | Hostinger | Provider-managed | Site content; contact-form mail relay |
| Managed devices | Customer's computers | Customer's premises | Agent config; offline queue; offline self-heal journal `%ProgramData%\SAVIO\offline-journal.jsonl` |

---

## 3. Processing activities

Retention below is **as implemented**. "Pruned on ingest" means old rows are removed when the
same device next reports; see gap G4.

### 3.1 Portal users of a customer organisation — *Processor*
| | |
|---|---|
| Data | Name, work email, role, active flag, hashed password (none for directory-only users), sign-in tokens, team memberships |
| Who it's about | The customer's staff given portal access, and directory-only users for asset assignment |
| Purpose | Sign-in, role-based access, assigning assets, routing approvals |
| Basis | Customer's instruction |
| Stored | Neon (`users`, `refresh_tokens`, `password_reset_tokens`, `user_team_members`) |
| Shared with | Resend (invites, resets, notifications) |
| Retention | Until the customer deletes or erases the user (Z2). Access tokens last 15 minutes; refresh tokens last 7 days and rotate |
| Access | Customer admins manage the users; technicians can list them. Technomate staff only through E1 view-as, while the customer's support-access window is open |

### 3.2 Device inventory and health telemetry — *Processor*
| | |
|---|---|
| Data | Hostname, OS, hardware, serial number, BIOS version and date, installed apps, services, Windows updates, event-log entries, CPU, RAM and disk samples, Windows activation status (never product keys), alert states |
| Who it's about | Indirectly the person using the device (hostnames like `ASHA-LAPTOP`) |
| Purpose | Diagnose and fix IT faults, compliance checks, early warnings, health-check report |
| Basis | Customer's instruction |
| Stored | Neon (`devices`, `device_*`, `telemetry_snapshots`, `telemetry_daily_rollups`, `alert_states`) |
| Shared with | Anthropic, only the parts relevant to a chat or diagnosis |
| Retention | Raw snapshots kept 7 days, pruned on ingest, never below a device's newest 60. Daily rollups kept for the life of the account. Inventory is replaced on each collection. All of it is deleted with the device |
| Access | Customer admins and technicians. Plain users see only their own device through the tray |

### 3.3 Signed-in identities on devices — *Processor*
| | |
|---|---|
| Data | Windows usernames (`DOMAIN\user`) of signed-in sessions, session state, logon time, idle seconds, RDP client name. Apps installed into a user's own profile. Local Windows accounts (name, full name, enabled, admin flag) |
| Purpose | Know who to help; per-user software inventory; local account management (A1) |
| Basis | Customer's instruction |
| Stored | Neon (`device_sessions`, `device_installed_apps` with scope `user`, `device_local_accounts`) |
| Retention | Replaced on each collection; deleted with the device or by Z2 erase (local accounts are only removed on the device itself) |
| Access | Customer admins and technicians |

### 3.4 Tracker / Workforce Insights (paid add-on, off by default) — *Processor*
| | |
|---|---|
| Data | Logon, logoff, lock, unlock and idle events per Windows username. The foreground app and, for browsers, the **website domain** (the **path** too, if the organisation chose path mode; never query strings). Idle and "input looked faked" flags. Derived work sessions, daily summaries and minutes per app or site with a productivity bucket |
| Who it's about | Employees, which makes this monitoring data |
| Purpose | Attendance, shifts and productivity reporting the customer switched on |
| Basis | Customer's instruction. The customer must have its own basis and must tell its staff (see gap G1) |
| Stored | Neon (`activity_samples`, `work_sessions`, `daily_user_summary`, `daily_app_usage`, `work_shifts`, `work_holidays`, `learned_categories`) |
| Shared with | Anthropic: app names and website domains the built-in list can't categorise are sent, without any username, to be put in a category (`workforce_ai.classify_new_activity`) |
| Retention | Raw `activity_samples` kept 90 days, pruned on ingest. **Derived sessions, summaries and app usage kept for the life of the account** (gap G5) |
| Access | Customer admins and technicians (Tracker API is staff-only; settings are admin-only). Erasable per person (Z2) |

### 3.5 AI conversations — *Processor*
| | |
|---|---|
| Data | Chat messages from portal and tray users, tool trail (which telemetry the AI read), AI-proposed fixes. Semantic answer cache: question text plus answer, per org |
| Purpose | IT support chat and diagnosis |
| Basis | Customer's instruction |
| Stored | Neon (`conversations`, `messages`, `semantic_cache_entries`, `support_escalations`) |
| Shared with | **Anthropic (United States)** via the commercial API. No training on API data; kept briefly for abuse monitoring. Freshservice, if the customer connected its own helpdesk (customer's system, not our sub-processor) |
| Retention | Life of the account; chats and escalations are erasable per person (Z2). The cache has no expiry and is not linked to a person (gap G6) |
| Access | **Only the user who started a chat** can list or read it, admins included (`ConversationService._get_owned`). Escalations raised from a chat are visible to the org's staff |

### 3.6 Actions and accountability — *Processor*
| | |
|---|---|
| Data | Remediation requests and approvals (who, what, why, result), software deployments, remote-session records (who asked, device, reason, allowed or declined, start and end), the organisation's audit log (every change and every agent command, with actor and detail) |
| Purpose | Human-in-the-loop control, security, proving what was done |
| Basis | Customer's instruction; security is a legitimate use |
| Stored | Neon (`remediation_tasks`, `deployments`, `remote_sessions`, `audit_logs`) |
| Retention | Life of the account. On Z2 erase, audit entries are pseudonymised, not deleted. **Audit logs and deployments outlive organisation deletion** (gap G3) |
| Access | Customer admins (audit log); admins and technicians (remediations, sessions) |

### 3.7 Remote support stream — *Processor*
| | |
|---|---|
| Data | Live screen, keyboard, mouse and clipboard of a session the person at the device allowed |
| Basis | Customer's instruction, plus the person's live consent for each session |
| Stored | Not stored: streamed through our relay (Singapore). The session record is under 3.6 |
| Retention | None for the stream. Relay VM logs: whatever MeshCentral keeps on that VM (gap G9) |
| Access | The requesting technician, during the session only |

### 3.8 Assets — *Processor*
| | |
|---|---|
| Data | Asset name, tag, serial, model, purchase and warranty dates, cost, location, who holds it, assignment history, acknowledgement emails |
| Stored | Neon (`assets`, `asset_events`) |
| Shared with | Resend (acknowledgement emails) |
| Retention | Life of the account; unlinked from a person on Z2 erase. **Outlives organisation deletion** (gap G3) |
| Access | Customer admins and technicians |

### 3.9 Account holder, sign-up and billing — *Fiduciary*
| | |
|---|---|
| Data | Sign-up (org name, admin name, email, hashed password, one-time code) until verified. Billing profile (legal name, contact, address, tax ID). Invoices. Payment-provider references (never card data) |
| Basis | Contract; invoices under legal obligation |
| Stored | Neon (`pending_registrations`, `organization_billing_profiles`, `invoices`, `webhook_events`) |
| Shared with | PayPal (wired in production). Razorpay and Paddle are listed publicly but have no production keys (gap G7). Resend |
| Retention | Pending sign-ups until verified or replaced. Billing records: 8 years from the end of the financial year (Companies Act / GST), per the privacy policy |
| Access | Customer admins; Technomate platform admins |

### 3.10 Website visitors and leads — *Fiduciary*
| | |
|---|---|
| Data | Contact or demo form fields (name, work email, phone, company, message), UTM and referrer, lead score and stage. Booking details. Analytics cookies |
| Basis | The person's request (enquiry); consent for marketing email and for cookies |
| Stored | Marketing service DB (`leads`, `lead_submissions`) |
| Shared with | Hostinger (form relay, mail), **n8n Cloud** (lead workflow), **Zoho Bigin** (CRM; one-way sync), **Telegram** (alert to the team with the lead's details), Cal.com (bookings), Google Analytics and Ads, Meta Pixel, Microsoft Clarity (website only, consent-gated). **Anthropic**: for lead scoring, the lead's message, company, email *domain*, interest and source (not name or email address); also marketing content drafting |
| Retention | Until the person asks for deletion (privacy policy) |
| Access | Technomate founder and team (admin token, Telegram chat, Bigin) |

### 3.11 Our operational logs — *Fiduciary (security) / Processor (content)*
| | |
|---|---|
| Data | Request logs (path, status, IP, user agent), application output that can include emails or hostnames, Cloud Build and job logs, Google audit logs |
| Basis | Legal obligation (CERT-In: 180 days in India); security as a legitimate use |
| Stored | Cloud Logging `_Default` (global, 30 days) and `india-logs` (Mumbai, 400 days), from Z1 |
| Access | Technomate staff with roles on the Google Cloud project (list in section 5) |

---

## 4. Technomate staff access to customer data

| Path | Control |
|---|---|
| Portal "view as" an organisation (platform admin) | Only while the customer's **support-access window** (E1) is open. Checked when the token is minted and on every request; audited with the operator's email |
| Production database | Direct SQL to Neon — **list who has it** (section 5) |
| Google Cloud project | IAM roles; Cloud Run, logs and Secret Manager |
| Remote-support relay VM | SSH / MeshCentral admin |

## 5. To fill in (founder)

- [ ] People at Technomate with production database, GCP or relay access, their role, and how that access is logged.
- [ ] Neon point-in-time restore / backup window, which bounds "backups expire within 30 days".
- [ ] Confirm the DPAs are in place (Z5): Google Cloud, Neon, Anthropic, Vercel, Resend, PayPal, Hostinger, n8n, Zoho, Telegram, Cal.com. Sentry is not used anywhere in the code, so drop it from the Z5 list.

---

## 6. Gaps found while drafting

Each item is a difference between what we publish and what the code does, or a choice nobody has written down. None was changed in this draft.

| # | Gap | Why it matters | Suggested fix |
|---|---|---|---|
| G1 | The privacy policy (§2.3) doesn't mention Tracker, and says the agent does not "monitor browsing history" | With Tracker on, the agent records the foreground app and **website domain** (path in path mode) per employee. A regulator or employee would read §2.3 as untrue | Add a Tracker section: what it records, that it is off unless the customer enables it, domain-only by default, retention |
| G2 | Privacy policy §2.3 predates Phase 1 | Local Windows accounts, apps in a user's profile, activation status, serial/BIOS, offline self-heal journal are not listed | Update §2.3 before the Phase 1 merge goes live |
| G3 | Deleting an organisation leaves `audit_logs`, `assets`, `asset_events`, `notifications`, `semantic_cache_entries`, `knowledge_articles`, `learned_actions`, `assistants` and `deployments` behind | These have `org_id` but no cascade, so the rows stay with a dead org ID. That contradicts "deleted from the live system" after closure | Delete them in `PlatformService.delete_organization`. Keep the audit log only if a retention period is written down |
| G4 | "Raw telemetry: 7 days" | Pruning runs only when that device next reports, and always keeps its newest 60. A device that goes silent keeps its last 60 snapshots indefinitely. Same pattern for Tracker raw samples (90 days) | Either word the policy accordingly, or add a periodic sweep (needs the Phase 2.0 scheduler) |
| G5 | Tracker derived data (sessions, daily summaries, per-app minutes) is never deleted | It is employee-monitoring history kept for the life of the account | Pick a cap (e.g. 13 months) with the lawyer (Z6) |
| G6 | AI answer cache has no expiry, and is not linked to a person, so Z2 erase can't find it | It stores question text, which can contain a name or problem detail | Expire entries (e.g. 90 days), or don't cache questions that mention a person |
| G7 | Public sub-processor list vs reality | Lists Razorpay and Paddle (no production keys exist, only PayPal). Doesn't list n8n Cloud, Zoho Bigin or Telegram, which receive lead data, yet privacy §3.2 says we share only with listed providers. Anthropic's row says "support conversations and telemetry" but it also gets Tracker app and site names, and lead messages. Doesn't show the India log bucket | Add a "marketing and sales tools" section; mark payment providers as "when enabled"; add Cloud Logging (India) |
| G8 | `MIGRATE_SRC_URL` / `MIGRATE_DST_URL` still in Secret Manager | Database credentials left over from the Railway → Neon move. A standing credential to customer data nobody uses | Delete if unused |
| G9 | Relay VM logs | MeshCentral keeps its own logs (who connected, when) on the VM, outside Cloud Logging and the India bucket. Retention unknown | Set MeshCentral log retention, or ship its logs to Cloud Logging |
| G10 | Old "Delete user" writes the email into the audit log | The plain delete leaves the person identifiable in the audit trail; only Z2 erase pseudonymises | Point the Users page delete at Z2 erase, or pseudonymise in `delete_user` too |
