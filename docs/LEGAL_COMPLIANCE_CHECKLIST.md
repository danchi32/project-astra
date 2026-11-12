# ASTRA — Legal, Tax & Compliance Checklist

Companion to [COST_MODEL_2K_DEVICES.md](COST_MODEL_2K_DEVICES.md) and
[COST_MODEL_10K_DEVICES.md](COST_MODEL_10K_DEVICES.md). This expands the "compliance" line
in both into an itemised list of registrations, documents and certificates.

> **This is a checklist to take to your CA and a lawyer — not legal or tax advice.** I am not
> qualified to conclude on any of it. Items marked **⚖️ confirm** are ones where the rule is
> genuinely contested, state-dependent, or has changed recently, and where a wrong assumption
> is expensive. Everything is written for an **Indian private limited company selling B2B SaaS
> to Indian and international customers**.

**Context that shapes this list:** ASTRA is not ordinary SaaS. The Windows agent runs with
system privileges on customer machines and **executes commands on them** — including registry
and service-level actions. That single fact drives the most important items here: the
authorisation clause in §3, the professional indemnity cover in §6, and the tiering evidence in
§5. Ordinary SaaS templates do not cover it.

**Repository status (2026-09-26):** published on the website — Privacy Policy, Terms of
Service (incl. the §3.1 remote-execution clause and remote support), Refund & Cancellation,
Cookie Policy, Agent EULA (also shown by the installer, `agent/install/EULA.txt`), Data
Processing Agreement, Acceptable Use Policy and the sub-processor list. These were drafted
in-house from what the software actually does and have **not** been reviewed by a lawyer —
a review is still recommended before the first enterprise contract. Internal documents in
`docs/legal/`: Mutual NDA template and Security Incident & Breach Notification policy.
Still outstanding: SLA (deliberately — see §3 item 6) and employment/contractor IP
assignment agreements.

---

## 1. Direct answer — what you need from the "VAPT / insurance / CA" line

| Item | Needed? | When | Cost |
|---|---|---|---|
| **VAPT (penetration test) — annual, with an attestation letter** | **Yes** | Before the first enterprise rollout | ₹3–6 L/yr |
| **Professional indemnity / E&O insurance** | **Yes — non-negotiable for ASTRA** | Before the first enterprise rollout | ₹1–2.5 L/yr |
| **Cyber liability insurance** | **Yes** | Before the first enterprise rollout | ₹0.75–2 L/yr |
| **CA — statutory audit, ROC + GST + TDS filings** | **Yes — statutory** | Already, ongoing | ₹1–2 L/yr |
| SOC 2 Type II | Only when a contract demands it in writing | Defer | ₹22–35 L yr 1 |
| ISO 27001 | Only when a contract demands it in writing | Defer | ₹8–15 L yr 1 |

**Why professional indemnity is non-negotiable here:** cyber liability covers *your* breach.
Professional indemnity covers **your software breaking the customer's machines** — an agent
release that bricks 500 endpoints, or a remediation that deletes something it shouldn't. For a
product with an execution agent, this is the policy that matters, and it is the one most often
forgotten. Make sure the policy explicitly covers **software errors and remote code execution
on client systems** — a generic IT policy may exclude exactly this.

---

## 2. Entity, tax & statutory registrations (your CA's domain)

### Must have before invoicing anyone

| # | Document | Issued by | Note |
|---|---|---|---|
| 1 | Certificate of Incorporation + CIN | MCA | |
| 2 | Memorandum & Articles of Association | MCA | Object clause must cover software/SaaS |
| 3 | Company PAN | Income Tax Dept | |
| 4 | **TAN** | Income Tax Dept | Required to deduct TDS — on salaries *and* on foreign vendor payments |
| 5 | **GST registration (GSTIN)** | GST Dept | Threshold is ₹20 L for services, but register regardless — you cannot claim input credit on ₹1–6 L/month of cloud spend without it |
| 6 | Current account + **AD Code** registration | Your bank | AD Code is what lets foreign payments land |

### Must have for international revenue

| # | Document | Note |
|---|---|---|
| 7 | **LUT (Letter of Undertaking), Form RFD-11** | Lets you export services **without paying IGST** and claiming it back. Filed **annually** on the GST portal — an expired LUT means you start paying 18% you'd have to reclaim |
| 8 | **IEC (Import Export Code)** — DGFT | ⚖️ **confirm** — for services it is not always mandatory, but banks routinely ask for it before releasing inward remittance |
| 9 | **FIRC / e-BRC** per inward remittance | Proof that export proceeds were realised; needed to substantiate the zero-rating in item 7 |

### Employment-related (triggered by headcount)

| # | Registration | Trigger |
|---|---|---|
| 10 | **EPF** | 20+ employees |
| 11 | **ESIC** | 10+ employees, for those earning ≤ ₹21,000/month |
| 12 | **Shops & Establishments** | State-level, from the first employee |
| 13 | Professional Tax | ⚖️ **confirm** — state-dependent; Delhi, Haryana and UP do not levy it, so a Delhi-NCR entity likely has nothing here |

### Ongoing filings

Statutory audit; ROC annual filings (**AOC-4**, **MGT-7**, **DIR-3 KYC**); monthly/quarterly
**GSTR-1 / GSTR-3B**; annual **GSTR-9**; quarterly **TDS returns** with Form 16/16A; advance
tax; **Form 15CA (and 15CB where applicable)** for each foreign remittance.

### Optional but worth having

- **DPIIT / Startup India recognition** — unlocks the §80-IAC tax holiday and angel-tax relief.
- **Udyam (MSME) registration** — brings you under the MSMED Act's 45-day payment protection,
  which is genuinely useful when enterprise customers stretch payment terms.

### ⚖️ Three tax questions to put to your CA explicitly

1. **TDS under Section 195 on foreign SaaS payments** (Google Cloud, Anthropic, Neon, Vercel,
   Sentry, Resend). The reference point is the Supreme Court's *Engineering Analysis* judgment
   (2021), which held that payments for off-the-shelf software to non-residents are not
   "royalty" and therefore not subject to TDS where no copyright is transferred. Whether each
   of your vendors falls inside that is your CA's call — get it in writing, because the
   downside is disallowance of the expense plus interest.
2. **GST reverse charge (RCM) @18% on imported services.** At 10,000 devices this is roughly
   ₹83,000/month of cash out, creditable but not free. Confirm the mechanics and whether a
   **GCP India billing entity** would be simpler than USD billing.
3. **Equalisation levy** — ⚖️ **confirm current status.** The regime has been progressively
   withdrawn; do not assume either way.

---

## 3. Customer-facing legal documents (a lawyer's domain)

None of these exist in the repository today.

| # | Document | Why it matters for ASTRA specifically |
|---|---|---|
| 1 | **MSA / Terms of Service** | The base contract. Must contain the §3.1 clause below |
| 2 | **Data Processing Agreement (DPA)** | You are a **processor** of the customer's employee and device data. Every enterprise buyer will require this |
| 3 | **Sub-processor list** (public page, with a change-notification commitment) | GCP, Neon, Anthropic, Vercel, Sentry, Resend, Razorpay/Paddle. Buyers check this; **Anthropic will be scrutinised** because customer telemetry reaches an AI vendor |
| 4 | **Privacy Policy** | Public, DPDP-compliant, naming a grievance officer |
| 5 | **Agent EULA** | Separate from the SaaS terms — this is software installed on the customer's machines |
| 6 | **SLA** | ⚠️ Sign one only when you have the team in §4 of the cost model to honour it. An uptime SLA is what forces the EM hire and 24×7 cover |
| 7 | **Acceptable Use Policy** | |
| 8 | **Mutual NDA template** | For every pilot conversation |
| 9 | **Employment agreements with IP assignment + confidentiality** | Without written assignment, the code your engineers write is not cleanly the company's |
| 10 | **Contractor agreements with IP assignment** | Same, and more often missed |
| 11 | **Security Incident / Breach Notification policy** | Referenced by the DPA; needs stated timelines |

### 3.1 The clause that matters most

Your MSA needs an **explicit written authorisation for remote execution**, covering:

- That the agent **executes commands on customer endpoints** with system privileges.
- The **three-tier model** — `automatic`, `approval_required`, `admin_only` — described in the
  contract, with the customer acknowledging which tiers they have enabled.
- Who inside the customer's organisation may approve tier-2 and tier-3 actions.
- **Limitation of liability for remediation outcomes** — capped, and carved out sensibly.
- The customer's warranty that they own or control the endpoints and are entitled to consent to
  monitoring of the employees using them.
- **Data residency**: your infrastructure is in **Singapore** (Cloud Run + Neon,
  `asia-southeast1` / `ap-southeast-1`). Indian customers will ask, and some will require India
  residency. Disclose it before the contract, not during the security review.

Without this clause you are running privileged code on someone else's machines on the strength
of a generic SaaS agreement. That is the single largest uninsured legal exposure in the
business.

---

## 4. Data protection

### India — DPDP Act 2023

⚖️ **Confirm the current enforcement timeline and rule text with counsel** — the Act is passed
and rules have been notified, but obligations phase in.

Practically you will need: a **privacy notice** in the required form; a lawful basis for
processing employee/device data (your customer is the Data Fiduciary, you are the Data
Processor — the DPA in §3 is what allocates this); a named **grievance officer** with published
contact details; a **breach notification** process to the Data Protection Board and to affected
principals; **data retention and deletion** policy — note your telemetry already prunes at 7
days with permanent daily rollups, which is a good story to tell, but it must be *written down*
to count; and a mechanism to honour data principal rights (access, correction, erasure).

### If you sell into the EU/UK — GDPR

A **DPA with SCCs** (Standard Contractual Clauses) for transfers out of the EEA; an **Article
30 record of processing activities**; a **transfer impact assessment** (your data sits in
Singapore); and possibly an **Article 27 EU representative**. Do not sell into the EU without
these — it is not a paperwork risk, it is a fines risk.

### If you sell into the US

CCPA/CPRA and the newer state privacy laws mostly land on you as contract terms rather than
registrations. Your customers' own compliance teams will drive the requirements.

---

## 5. Security artifacts buyers will ask for

At 2,000–10,000 endpoints, every serious buyer runs a vendor security review. What they ask for,
in the order they usually ask:

| # | Artifact | Have it? |
|---|---|---|
| 1 | **Completed security questionnaire** (CAIQ, SIG Lite, or their own) | Build one canned answer set — you will fill this in dozens of times |
| 2 | **Current VAPT report + attestation letter** | Annual, §1 |
| 3 | **Security whitepaper / architecture overview** | Write once. Cover the RBAC model, JWT lifetimes, audit logging, the command allowlists, and the tier enforcement |
| 4 | **Information security policy set** | Needed even without certification — access control, incident response, change management, vendor management, BCP/DR, data retention |
| 5 | **Code-signing certificate** | Already planned (Azure Trusted Signing). This is a **trust artifact, not just an engineering one** — an unsigned agent that Defender quarantines is a failed deployment |
| 6 | **Evidence of approval-tier enforcement** | Specific to ASTRA: buyers will want proof that tiering is enforced in code, not merely in the AI prompt. Your architecture already does this — document it |
| 7 | **Audit log capability** | Contractual in most enterprise deals: who ran what, on which device, approved by whom |
| 8 | SOC 2 Type II / ISO 27001 | Only when demanded — §1 |

Items 1, 3, 4 and 6 cost **time, not money**, and remove most of the pressure to buy SOC 2
early. Doing them well is the cheapest compliance decision available to you.

---

## 6. Insurance

| Policy | Needed | Cover | ₹/yr |
|---|---|---|---|
| **Professional indemnity / E&O** | **Critical** | Your software damaging customer systems. Verify it covers software errors and remote execution on client systems | 1–2.5 L |
| **Cyber liability** | **Yes** | Your own breach: data loss, notification costs, forensics, extortion | 0.75–2 L |
| Commercial general liability | Standard | | 0.25–0.5 L |
| Directors & Officers | Only if raising external funding | Usually an investor requirement | 1–3 L |
| Group health / personal accident | Retention, plus ESIC-adjacent | | per headcount |

Buy professional indemnity and cyber together from one insurer — split policies create gaps at
exactly the boundary where an ASTRA incident would land.

---

## 7. Intellectual property

| Item | Note |
|---|---|
| **Trademark — "ASTRA" and your logo, Class 9 and Class 42** | ⚠️ Search first. "Astra" is a heavily used mark across sectors; a clearance search before filing is cheaper than a rebrand after a customer launch |
| Domain ownership consolidated under the company | Not a founder's personal account |
| Copyright | Software is protected automatically in India; registration is optional and rarely worth it |
| IP assignment from **every** employee and contractor | §3, items 9–10. This is what a future acquirer or investor will diligence first |

---

## 8. Priority — what to do when

### Now (before the next customer contract)

Entity items 1–6 and 10–13 (§2) · LUT (§2 item 7) · MSA with the §3.1 execution clause · DPA ·
Privacy Policy · Agent EULA · Sub-processor page · Mutual NDA · IP assignments from everyone
who has written code · Trademark clearance search.

**Cost: ₹3.5–6 lakh, mostly one-time legal fees.**

### Before the 2,000-device enterprise rollout

VAPT + attestation · Professional indemnity + cyber insurance · Security questionnaire answer
set · Security whitepaper · Information security policy set · Audit-log and tier-enforcement
evidence pack · Code-signing certificate live.

**Cost: ₹5–10 lakh in year 1.**

### Only when a signed contract requires it

SOC 2 Type II (₹22–35 L) · ISO 27001 (₹8–15 L) · India data residency (a second deployment
region — an **infrastructure cost**, not a compliance fee, and a significant one) · EU
representative and full GDPR apparatus.

### Deliberately not yet

D&O insurance (until you raise) · Copyright registration · Any certification bought
speculatively.

---

## 9. Cost reconciliation with the cost models

| Block | 2,000 devices | 10,000 devices |
|---|---|---|
| Now — legal foundation (one-time) | ₹3.5–6 L | ₹3.5–6 L |
| Before rollout — VAPT + insurance + policies (yr 1) | ₹5–10 L | ₹6–13 L |
| Recurring — VAPT, insurance, CA, filings | ₹6.5–12 L/yr | ₹8–16 L/yr |
| SOC 2 + ISO, **if demanded** | +₹30–50 L yr 1 | +₹30–50 L yr 1 |

This matches the compliance lines already carried in both cost models. The **only** item that
would materially move those totals is SOC 2 / ISO — which is why the recommendation in both
documents is to hold it until a contract names it.
