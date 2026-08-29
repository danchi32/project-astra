# ASTRA Marketing Service

System of record for marketing: leads today, content and approvals next. FastAPI +
PostgreSQL, deployed to Cloud Run like the product backend but as its **own service with
its own database**.

## Why this is not part of `backend/`

The product API executes commands on customer endpoints. This service holds marketing
OAuth tokens and exposes a publicly reachable write endpoint. Putting the two in one
process widens the blast radius of the most sensitive code in the company for no benefit,
so they share patterns and nothing else — no imports, no shared database, no foreign keys
between a lead and a customer record.

## The one rule

Everything downstream of capture may fail. Capture may not.

`POST /leads/intake` commits the lead **before** it tries to notify anyone. If n8n is down,
the submission keeps `dispatched_at = NULL` and the replay sweeper finds it. If SMTP is
down, `contact.php` still reports success because the lead is stored. The failure this
service exists to prevent is a visitor who believes they made contact when no record of
them exists anywhere.

## Layout

| Path | Purpose |
|---|---|
| `app/core/config.py` | Settings, `ASTRA_MKT_` prefix. Two secrets fail **shut**; everything else is inert until set. |
| `app/core/security.py` | HMAC request signing shared with `website/hostinger/contact.php`. |
| `app/models/lead.py` | `Lead` (one per person, unique email) + `LeadSubmission` (one per form fill, carries its own attribution). |
| `app/services/leads.py` | Capture, dedupe, consent. Commits before anything that can fail. |
| `app/services/dispatch.py` | Signed hand-off to n8n. Never raises. |
| `app/api/v1/leads.py` | Intake (signed) and read endpoints (admin bearer token). |

## Lead scoring

The rubric is **not invented here**. `docs/GO_TO_MARKET.md` states the bar — *"a work
email, 50+ Windows endpoints or clear MSP fit, a relevant pain, and a buyer/champion"* —
and those four clauses are the four components in `app/services/scoring.py`. The
exclusions in the same document (non-Windows fleets, and the obvious non-buyers) are the
disqualifiers. When the sales rule changes, that document changes first and this file
follows; a score the founder cannot recognise as their own qualification rule is a score
they will ignore.

Two layers:

| | Runs | Needs | Can it decide? |
|---|---|---|---|
| **Rules** | Inline at capture | Nothing | Yes — sets score, tier, and DISQUALIFIED |
| **Model** (Haiku 4.5) | `POST /leads/{id}/rescore`, from the automation | `ASTRA_MKT_ANTHROPIC_API_KEY` | Only ±15 points |

The split is why the visitor's form never waits on an API call, and why an unset key costs
nothing: every lead is scored and tiered before the response is sent.

`HOT ≥ 65`, `WARM ≥ 35`. HOT means *a human replies personally, today* — set high enough
that the label stays trustworthy. A stated fleet below the ICP floor **caps** the total
rather than merely discounting it: awarding few points was not enough, because a work
email plus a described pain still carried a twelve-device shop into WARM.

**The message is untrusted input.** It is quoted between `<message>` markers and the model
is told it is data. The real defence is structural, though: the only thing the model can
return is a bounded integer and three flags, so the worst a successful prompt injection
achieves is fifteen points the lead could have earned honestly. `rescore` also only ever
moves a lead *into* DISQUALIFIED, never out of one a human set.

## Notifications

Two separate promises, tracked in two separate columns:

| | Column | Who it is for |
|---|---|---|
| Acknowledgement email | `acknowledged_at` | The prospect — confirms the enquiry landed, carries the Cal.com link |
| Telegram alert | `notified_at` | The team — score, reason, the message, and a `mailto:` to reply |

Either can fail without the other. A null on a lead older than a minute is a broken
pipeline worth alerting on, not a mystery.

Both run **inline**, concurrently, after the commit — not as FastAPI background tasks.
Cloud Run throttles CPU outside the request by default, so work scheduled after the
response is starved and may never run: the visitor would get a fast form and no email.
Together they cost a few hundred milliseconds and neither can raise.

The acknowledgement is not pretending to be a human. It says the enquiry arrived, offers
the calendar, and says a person will follow up — a prospect who books from it has
converted with nobody touching it, and one who waits has still been answered. It is
skipped for anyone with `unsubscribed_at` set.

Telegram is **outbound only**. No webhook, no inline keyboard: buttons mean a public
callback endpoint that can change state, and that gets designed once, carefully, with the
content approval desk. Every field in the alert is HTML-escaped — name, company and
message all come from a public form, and a lead crafted to make Telegram reject the
message would otherwise silently stop the alerts.

## CRM sync (Zoho Bigin)

One-way: this service writes to Bigin and never reads lead data back. A human editing a
company name there should not have it overwritten by the next form fill, and a human
moving a deal forward is the authority on where it is.

Two facts here were **read from the live org**, and both would have been wrong as guesses:

- The records module is **`Pipelines`**. `/Deals` 404s — though `settings/fields?module=Deals`
  works, which is a legacy alias on the metadata endpoint only.
- A Pipeline record has **three** mandatory fields: `Deal_Name`, `Stage`, `Sub_Pipeline`.
  Omitting the last one fails the create.

Stage names come from `docs/GO_TO_MARKET.md`, not from Bigin's defaults, and the org's
stages were renamed to match. `BiginClient.verify_stages()` reports any the code expects
and the org lacks — worth calling at deploy time, because a renamed stage otherwise
surfaces as one lead at a time failing weeks later in a log nobody reads.

`POST /leads/{id}/sync-crm` is deliberately **out of the intake path**: two API round trips
is one to two seconds, and nothing depends on the CRM being current within the minute.
`POST /leads/sync-pending` sweeps every lead that never reached it — one failure never
stops the batch, or a single rejected lead would block every lead behind it forever.

Contacts are upserted on email and the pipeline record is created only when
`crm_record_id` is null, so a retry after a partial failure cannot produce a second deal.

### Getting the credentials

Zoho's API Console is region-specific: an India-DC Bigin org needs
[api-console.zoho.in](https://api-console.zoho.in), and credentials from the `.com`
console will not work against `.in`. Create a **Self Client** (not client- or
server-based — nobody logs in; the service acts unattended as one fixed account), then on
the *Generate Code* tab use scope:

```
ZohoBigin.modules.ALL,ZohoBigin.settings.modules.READ,ZohoBigin.settings.fields.READ
```

The settings scopes are read-only and exist so the code can check the org's real stage and
field names rather than assume them. The authorization code expires in minutes and is
single-use; exchange it immediately for a refresh token, which does not expire.

## Local development

Python **3.11** — the same version the backend's image and CI use.

```bash
cd marketing-service
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env        # then fill in ASTRA_MKT_DATABASE_URL
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8100
```

The test suite runs entirely on in-memory SQLite and makes no outbound requests — the n8n
webhook is deliberately unset in `tests/conftest.py`, so a test can never post a fake lead
to a real automation.

## Deployment

Cloud Run, `asia-southeast1`, project `astra-prod-503923` — the same region as the product
backend and as Neon, because cross-region compute→DB adds ~40 ms to *every* query and each
request makes several.

| | |
|---|---|
| Service | `astra-marketing` |
| URL | `https://astra-marketing-fmuizr4sda-as.a.run.app` |
| Migration job | `astra-marketing-migrate` |
| Image | `asia-southeast1-docker.pkg.dev/astra-prod-503923/astra/marketing` |
| Workflow | `.github/workflows/deploy-marketing.yml` (push to `main` touching `marketing-service/**`) |

**`max-instances` is 2, and that is a deliberate floor.** Cloud Run's regional CPU quota is
*project-wide* — 20 vCPU here, which is why `astra-backend` is capped at 20 — and
`astra-backend-staging` already claims up to 3 on top of that. Every instance this service
reserves is capacity the product API cannot scale into. At concurrency 40, one instance
covers this workload many times over; the second exists only so a deploy's revision
overlap is never the thing that blocks it.

`min-instances` is 0. Measured cold start is ~1.5 s, and a warm intake completes in ~2.9 s
including the acknowledgement email and the Telegram alert. An always-warm instance would
cost more per month than the rest of the marketing stack combined, and buys back only that
1.5 s. Note also that a cold start cannot lose a lead: `contact.php` gives up after 6 s,
but the request has already reached this service, which commits regardless of whether the
caller is still listening.

Secrets live in Secret Manager, each granted to the runtime service account individually
rather than at project level — the same least-privilege pattern the backend's secrets use.

## Migrations

Alembic, never by hand. On Cloud Run they run once from the `astra-marketing-migrate` Job
before the revision rolls, not from the container entrypoint — parallel cold-starting
instances would otherwise race on `alembic upgrade`.

```bash
.venv/Scripts/python -m alembic upgrade head          # local
.venv/Scripts/python -m alembic revision -m "..."     # new revision
```

## Wiring the website to it

1. Generate a secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. Set it as `ASTRA_MKT_INTAKE_SECRET` on the service.
3. Put the **same** string as `intake_secret` in `website/hostinger/mail-config.php`
   (see `mail-config.example.php`), along with `intake_url`.

`mail-config.php` is gitignored and excluded from the website's FTP deploy, so it survives
releases. Until both values are present, `contact.php` behaves exactly as it did before —
it mails the enquiry and records nothing.

## Security notes

- **Intake is signed, not tokenised.** The HMAC covers the timestamp and the raw body, so
  a captured request is not replayable and a leaked proxy log does not yield a credential.
  Requests older than `intake_max_skew_seconds` (300) are refused.
- **The read endpoints return personal data** — names, work emails, phone numbers, message
  text — and require `ASTRA_MKT_ADMIN_TOKEN`. An unset token closes them rather than
  opening them.
- **Nothing is hard-deleted.** A disqualified lead is how the scorer learns, and an
  unsubscribed one must be remembered precisely so it is never emailed again.
- **Consent is stored as text, not a boolean** (`consent_source`, `consent_at`), because
  the DPDP Act asks what the person actually agreed to, not whether a checkbox was ticked.
