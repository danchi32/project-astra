# ASTRA — full-product test pass

Date: 2026-08-08 · Scope: backend (`app/`), all 144 routes, all service modules ·
Method: static route audit + coverage + behavioural tests run against the real services

Every finding below was **reproduced**, not inferred from reading code. The repro is given
so anyone can re-run it.

**Status: H1, M1, M2 and M3 are fixed**, each with a regression test that was confirmed to
fail against the old code. See "What was fixed" at the end. I1 is not a bug (a scope
statement), and I2 is a rollout decision that belongs to the operator, not to this pass.

---

## Summary

| | |
|---|---|
| Test suite | **646 passed**, 0 failed (13m34s) |
| Line coverage | **77%** (7,963 statements, 1,855 uncovered) |
| Routes audited | **144** — 15 unauthenticated, all legitimately public |
| IDOR sweep | **0 found** |
| Findings | 1 high, 3 medium, 2 informational |

The single most useful correlation: **every functional finding below sits in code no test
executes.** The suite is green because it does not go there.

---

## H1 — Knowledge base returns *nothing* when the user's wording differs

Severity: **High** (functional) · `app/services/ai/knowledge.py:150`, `app/services/ai/aliases.py:78`

Five articles were loaded and searched with six ordinary user phrasings. Two returned zero
results — not a bad ranking, **no answer at all**:

```
outlook khul nahi raha                   -> Outlook won't open            PASS
outlook not opening                      -> Outlook won't open            PASS
wifi disconnect ho raha hai baar baar    -> (nothing)                     FAIL
my c drive is out of space               -> (nothing)                     FAIL
cannot print anything                    -> Printer offline               PASS
mic not working in teams call            -> Teams microphone not working  PASS

top-1 accuracy: 4/6
```

Cause, measured directly against the embedding provider (`hash-v2-256`):

```
'wifi disconnect ho raha hai baar baar'  tokens=['wifi','disconnect','baar','baar']
   best similarity 0.000  (search threshold is 0.2)
'my c drive is out of space'             tokens=['c','driv','out','spac']
   best similarity 0.000
```

`"Wi-Fi"` tokenises to `['wi','fi']`; the user types `wifi`, one token. Zero overlap, so
cosine similarity is **exactly 0.0**. `"c drive out of space"` shares no token at all with
`"Disk is full / temp folders / recycle bin"`.

The design already anticipates this — `aliases.py` asks an LLM at write time for the words a
user would actually type. It works:

```
NO aliases   0.000  'wifi disconnect ho raha hai baar baar'  -> NOTHING
WITH aliases 0.612  'wifi disconnect ho raha hai baar baar'  -> found
```

**The problem is what happens when alias generation doesn't run.** `for_article()` returns
`[]` — never raises — when there is no `ASTRA_ANTHROPIC_API_KEY`, and on any LLM failure
(rate limit, timeout, malformed reply). That trade is right for the write path: losing a
technician's article is worse than losing recall. But the consequence is unmanaged:

- The article is stored with **no aliases and no marker**.
- There is no retry, no backfill, and no "articles with no aliases" report.
- The symptom is "the assistant doesn't know things", months later, with no trail back.

Production has the key (`/health` reports `ai_enabled: true`), so new articles are fine
*today*. Any article written during an LLM outage is permanently degraded and invisible.

**Repro:** load five articles via `KnowledgeBaseService.create`, search the six phrasings.
**Suggested fix:** record whether aliases were generated (`symptom_samples is None` already
distinguishes it); a backfill job for articles missing them; and surface the count to
operators the same way the stale-embedding warning already is.

---

## M1 — Billing webhooks can be replayed, and arrive out of order, with no guard

Severity: **Medium** · `app/services/billing.py:165`

`apply_event` applies whatever it is handed:

```python
if event.status is not None:
    org.subscription_status = event.status
if event.quantity is not None:
    org.license_count = event.quantity
```

There is no event id, no dedupe table, and no comparison against what is already stored.
Signature verification is solid — all three HMAC rails use `hmac.compare_digest` and refuse
when the secret is unset, and PayPal verifies with PayPal — but a signature proves
*authenticity*, not *freshness*.

Two consequences:

1. **Replay.** Paddle's scheme signs `ts:body` but nothing checks that `ts` is recent;
   Razorpay signs the body only. A captured `subscription.activated` payload stays valid
   forever, and replaying it after cancellation flips `subscription_status` back to ACTIVE
   and restores `license_count` — that is the flag `org_is_writable` reads.
2. **Ordering.** No rail guarantees delivery order. A delayed `activated` landing after
   `canceled` leaves a cancelled org active. This needs no attacker at all.

**Suggested fix:** persist the provider event id and ignore ones already applied; reject
Paddle signatures whose `ts` is older than ~5 minutes; ignore an event older than the one
already recorded on the org.

---

## M2 — A trailing space in `plan` grants the entire product

Severity: **Medium** (revenue) · `app/services/entitlements.py:90`

```
plan='essential'     ->  6 features
plan=' essential '   -> 16 features   EXTRA: advanced_rbac, ai_act, approval_tiers,
                                             audit_export, banned_software, compliance,
                                             employee_chat, fleet_correlation,
                                             fleet_remediation, lockdown
```

`features_for` does `PLANS.get((plan or "").lower(), _EXPERT)` — it lowercases but does not
strip. Falling back to Expert for an *unknown* plan is a deliberate, documented choice and I
agree with it: a typo must not switch a paying customer's product off. But whitespace is not
an unknown plan, it is the same plan with a space, and it silently upgrades an Essential
customer to everything.

It is also inconsistent with its own neighbour: `requires()` calls `normalise_plan(org.plan)`
for the error message but passes the **raw** `org.plan` to `features_for` for the grant.

**Repro:** `features_for(" essential ")`.
**Suggested fix:** `.strip()` in `features_for`, or route every caller through
`normalise_plan` first.

---

## M3 — Restricted-software patterns are unescaped LIKE patterns

Severity: **Medium** · `app/services/compliance.py:187`

```python
conds = [func.lower(DeviceInstalledApp.name).like(f"%{b.pattern}%") for b in banned]
```

`pattern` is admin-supplied and lowercased, but `%` and `_` reach SQL as wildcards.
Reproduced against a device with 8 installed apps:

```
pattern 'utorrent'         -> 1 match : ['uTorrent']                       correct
pattern 'teamviewer_host'  -> 1 match : ['TeamViewer_Host']                correct by luck
pattern 'zoo_'             -> 1 match : ['Zoom']                           underscore = wildcard
pattern '%'                -> 8 matches: every app on the device
```

One stray `%` makes every device in the fleet fail the *No restricted software* check.
`_` is the more likely accident — real product names contain it (`TeamViewer_Host`,
`Zoom_Installer`), and an admin pasting one gets a pattern that matches more than they typed.

Not a privilege escalation — an admin sets these — but compliance scoring is a reported,
customer-facing number, and this corrupts it silently. There is also no minimum length, so
a one-character entry fails nearly every device.

**Suggested fix:** escape `%`, `_` and `\` and pass `escape="\\"` — the same fix already
applied to `requester.py` today — plus a minimum pattern length.

---

## I1 — "Application blocker" is detection only

Informational · `app/models/banned_software.py:12`

Worth stating plainly because the name suggests otherwise. The model's own docstring:

> *"A device fails the 'no banned software' compliance check when any installed app name
> contains `pattern`. Detection only — nothing is uninstalled automatically."*

What exists: an org-scoped list (`GET/POST/DELETE /compliance/banned-software`, admin to
write), substring matching against collected app inventory, a compliance check, and audit
entries on add/remove. What does not exist: blocking execution, preventing installation, or
uninstalling. No remediation action in the registry does it either — the 22 registered
actions contain nothing of the kind.

---

## I2 — Agent rate limiting is log-only in production

Informational · `app/core/config.py:65`

`agent_rate_limit_enabled: bool = True` but `agent_rate_limit_enforce: bool = False`. The
limiter counts and logs; it never returns 429 unless `ASTRA_AGENT_RATE_LIMIT_ENFORCE` is
set. That was the deliberate rollout plan; it is still unset, so at 1,000–2,000 devices
there is currently no server-side brake on a misbehaving agent.

`/agent/enroll` has no limiter at all (it cannot be device-keyed — there is no device yet).
The enrollment key is `secrets.token_urlsafe(48)` (384 bits) so it is not guessable, and the
licence cap bounds how many devices can be created.

---

## What was checked and found clean

- **Route audit, 144 routes.** 15 have no auth dependency: login, register (+start/verify),
  password reset (×2), refresh, logout, the four billing webhooks, `agent/enroll`,
  `assets/acknowledge`, `downloads/uninstaller`. Every one is legitimately public. The
  first run of my audit script reported 55 — that was my bug, it did not resolve
  module-level aliases like `staff_required = require_roles(...)`; corrected before use.
- **Cross-tenant access (IDOR).** Swept every single-row lookup by id across all services.
  Four had no org check within seven lines; all four verified correct by hand — two are
  global-only deletes that assert `org_id is None`, one is device-scoped
  (`record_result` checks `task.device_id != device.id`), one is reached only through an
  already-scoped conversation. **No IDOR found.**
- **Caller-supplied org ids.** Only 12 routes take one, all in `platform.py`, all behind
  `require_platform_admin`. No org-scoped route accepts an org id from the caller.
- **Remediation tiers vs CLAUDE.md.** 22 registered actions; every one sits at the tier the
  spec names. `admin_only` = registry_fix, reset_windows_update_components,
  disable/enable_local_account. BIOS, firmware and Windows-reinstall are **not implemented
  at all**, which is the safer answer than implementing them.
- **Public token entropy.** Device tokens, enrollment keys and asset acknowledgement tokens
  are all `secrets.token_urlsafe(48)`.
- **Webhook signature verification.** Razorpay and Paddle HMAC-SHA256 with
  `compare_digest`; both refuse when the secret is unconfigured. PayPal verifies through
  PayPal's own endpoint and requires all five signature headers.
- **Security-critical modules at 100% coverage:** `api/deps.py`, `core/security.py`,
  `core/crypto.py`, `services/entitlements.py`.

---

## Coverage: where the tests are not

77% overall. The gaps are all service-layer business logic, and they are where the findings
above live — `compliance.py:183-193`, the banned-software query, is in the uncovered range.

| Module | Coverage | Why it matters |
|---|---|---|
| `services/platform.py` | **30%** | The most privileged code there is — delete org, set discount, mint view-as tokens |
| `services/auth.py` | **40%** | Registration, OTP, password reset, refresh rotation |
| `services/agent_update.py` | 40% | Signed fleet update channel |
| `services/compliance.py` | 41% | Contains M3 |
| `services/assets.py` | 41% | |
| `services/email_integration.py` | 42% | |
| `services/reports.py` | 43% | |
| `services/agent_installer.py` | 44% | |
| `services/users.py` | 46% | |
| `services/email_domains.py` | 49% | |
| `services/telemetry.py` | 51% | Ingest path for every device |
| `services/locations.py` | 52% | |
| `services/devices.py` | 53% | Enrolment (151-207) uncovered |
| `services/dashboard.py` | 53% | |
| payments providers | 54–63% | Contains M1 |

If only one gets tests, make it `platform.py`: 30% coverage on the operations that can
delete a customer's organisation.

---

## Not covered by this pass

Stated so the green numbers are not read as more than they are.

- **The C# Windows agent.** No xUnit run here; this pass was backend only.
- **The portal.** Vitest + typecheck run in CI and pass; no UI test campaign here.
- **Migrations.** Still never execute in the suite (see `TESTING-NOTES.md`); 0040–0043 were
  verified by hand on staging.
- **Load and concurrency.** No test of 1,000–2,000 devices heartbeating, which is the
  stated LanceSoft target.
- **The live Freshservice path.** Still blocked on the trial.

---

## What was fixed

Each fix was checked the same way: write the regression test, confirm it **fails** against
the old code, then apply the fix. A test that passes either way proves nothing.

**H1 — knowledge base recall.** `AliasGenerator.for_article` now returns `None` when it
never got to ask, and `[]` when the model answered with nothing — those were both `NULL`
before, so nothing could tell a fixable article from a finished one. A new
`knowledge_articles.aliases_generated_at` column records the difference (migration 0045,
which also stamps existing rows that already have aliases). `scripts/backfill_aliases.py`
regenerates and re-embeds the rest, and `search()` now warns with a count the same way the
stale-vector check already did.

The column exists because `symptom_samples IS NULL` **does not work**: SQLAlchemy writes a
Python `None` into a JSON column as the JSON value `'null'`, which is not SQL NULL. The
Python side reads back `None` either way, so the first version of the backfill reported
"0 articles affected" and did nothing while looking successful. The test caught it.

**M1 — webhook replay and ordering.** New `webhook_events` table (migration 0044) with a
unique `(provider, event_id)`. `apply_event` refuses a delivery it has already applied and
one whose `occurred_at` is older than the org's newest, and it relies on the constraint
rather than an `if exists` check so two racing deliveries cannot both win. Paddle deliveries
older than 5 minutes are now rejected outright — Paddle signs the timestamp precisely so
this is possible, and nothing was reading it. All three rails now hand up their event id and
timestamp.

The existing Paddle tests signed a hardcoded `ts=1700000000`, which the new check correctly
treats as a replay. The fixture defaults to *now* now, because that is what a real delivery
carries. It was also missing `event_id` and `occurred_at`, which every real Paddle payload
has — so the dedupe could have shipped reading `None` from a field that is always present.

**M2 — plan whitespace.** `features_for` and `normalise_plan` now share one `_plan_key`, so
what the admin is told and what they are granted are derived from the same reading of the
same string. `" essential "` is Essential again.

**M3 — restricted-software patterns.** `%`, `_` and `\` are escaped and passed with
`escape="\\"`, and a pattern shorter than three characters is refused with an explanation
rather than silently failing the fleet.

### Not fixed, deliberately

**I1** is not a bug — it is what the feature is. If restricted software should be blocked or
uninstalled rather than reported, that is a new feature with its own tier decision, not a
repair.

**I2** is a rollout decision. Setting `ASTRA_AGENT_RATE_LIMIT_ENFORCE=true` starts returning
429 to real agents in the field, and choosing when to do that belongs to whoever is watching
the fleet.
