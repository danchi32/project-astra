# ASTRA Backend Migration Runbook — Railway → Google Cloud Run + Neon

Status: **CUTOVER COMPLETE (2026-07-30).** `api.astra.technomateai.com` is served by Cloud
Run against Neon. Railway is retained, idle, as rollback insurance for one week.

| | |
|---|---|
| GCP project | `astra-prod-503923` |
| Region | `asia-southeast1` (Singapore) |
| Live service | `astra-backend` — `https://api.astra.technomateai.com` (also `*.run.app`) |
| Database | **Neon Postgres 18**, `ap-southeast-1`, pooled endpoint, 7-day history window |
| Certificate | Google Trust Services, auto-renewing (issued 2026-07-30) |
| Auto-deploy | `.github/workflows/deploy-backend.yml` — push to `main` touching `backend/**` |
| Railway | idle, retained until ~2026-08-06 for rollback |

> The portal stays on **Vercel**. Its `NEXT_PUBLIC_API_URL` must be
> `https://api.astra.technomateai.com` — it pointed straight at a Railway URL before the
> cutover, which would have left the portal reading the old database while agents wrote to
> Neon.

## ⚠️ Post-cutover: never run `astra-dbcopy` again

It does a **full replace** of the destination. That was right while Neon was a standby; now
Neon is live, so a re-run would destroy production and restore stale Railway data. The Cloud
Run job was **deleted** at cutover, and `deploy/dbcopy/copy.sh` now refuses to run unless
`I_UNDERSTAND_THIS_REPLACES_THE_DESTINATION=yes` is set. `astra-dbcheck` (read-only) stays.

---

## 0. Golden rule — keep the domain, and the agents never notice

Every installed agent (and every installer already handed out) has the backend URL baked
in: **`https://api.astra.technomateai.com`**. Enrollment and the auto-update manifest all
resolve through that host.

**So: keep the same domain.** We repoint it at Cloud Run instead of Railway. Agents keep
calling the identical URL — **no re-install, no config push, no agent release**. Migration
becomes "swap what's behind the domain," and rollback is one DNS change.

---

## 1. Architecture (as actually deployed)

```
Windows Agents ─┐
                ├─ https://api.astra.technomateai.com ─→ [today: Railway]
Vercel Portal ──┘                                        [after flip: Cloud Run]

Cloud Run  astra-backend   asia-southeast1, min=1, max=10, concurrency 80
    │
    └─→ Neon Postgres 18   ap-southeast-1 (Singapore), POOLED endpoint
Secrets   → Google Secret Manager   (11 secrets, ASTRA_ prefixed)
Images    → Artifact Registry       asia-southeast1/astra
Jobs      → astra-migrate (alembic) · astra-dbcopy (Railway→Neon data copy)
```

**Why Singapore, not Mumbai:** Cloud Run is co-located with Neon. Cross-region compute→DB
would add ~40 ms to *every query*, and a single API request makes several. India→Singapore
adds ~40 ms once per request; DB round-trips stay ~1–2 ms. Co-location wins.

**Not used by this backend** (verified in code, so no accounts needed):
- **Redis** — no redis client anywhere; the semantic cache is a DB table.
- **Qdrant** — only named in a comment in `semantic_cache.py`; knowledge search doesn't use it.

---

## 2. Environment variables — note the `ASTRA_` prefix

`config.py` sets `env_prefix="ASTRA_"`, so every setting is read as `ASTRA_<FIELD>`.
Getting this wrong makes the service start and then fail validation.

**Secrets in Secret Manager** (11): `ASTRA_DATABASE_URL`, `ASTRA_JWT_SECRET_KEY`,
`ASTRA_ANTHROPIC_API_KEY`, `ASTRA_RESEND_API_KEY`, `ASTRA_EMAIL_FROM`,
`ASTRA_PAYPAL_CLIENT_ID`, `ASTRA_PAYPAL_CLIENT_SECRET`, `ASTRA_PAYPAL_PLAN_ID`,
`ASTRA_PAYPAL_WEBHOOK_ID`, `ASTRA_BOOTSTRAP_ADMIN_EMAIL`, `ASTRA_BOOTSTRAP_ADMIN_PASSWORD`.

Billing is **PayPal** on this deployment (no Razorpay/Paddle values are set).

**Non-secret env** — see `backend/deploy/env.cloudrun.example`; the deploy script sets them.

`ASTRA_JWT_SECRET_KEY` is the **same value as Railway** — reusing it means existing
sessions survive the flip. A new value would sign everyone out.

**CORS** is unset here just as on Railway: the portal calls the API through its own
Next.js rewrite (same-origin), so no CORS entry is needed.

---

## 3. What's already done (one-time setup)

- [x] APIs enabled: run, artifactregistry, secretmanager, cloudbuild
- [x] 11 secrets copied Railway → Secret Manager via `deploy/migrate-secrets.py`
      (values piped on stdin — never printed, logged, or written to disk)
- [x] Runtime SA `…-compute@developer.gserviceaccount.com` granted
      `roles/secretmanager.secretAccessor` on every secret
- [x] Artifact Registry repo `astra` (asia-southeast1)
- [x] Neon project (Postgres 18, Singapore), pooled + direct endpoints
- [x] `astra-migrate` job → `alembic upgrade head` ⇒ schema at **0034**
- [x] `astra-backend` service deployed and smoke-tested
- [x] Production data copied in (see §5)

---

## 4. Redeploying the standby

From `backend/`:
```bash
./deploy/cloudrun-deploy.sh
# gcloud not on PATH? →  GCLOUD='C:\Users\…\gcloud.cmd' ./deploy/cloudrun-deploy.sh
```
It builds via **Cloud Build** (no local Docker daemon needed), runs the migration **Job**,
then deploys the service. It never touches DNS.

Two things the script encodes that are easy to get wrong:
1. `RUN_MIGRATIONS_ON_START=false` — `entrypoint.sh` would otherwise run `alembic upgrade`
   on every instance, and parallel cold starts race. Migrations run once, in the Job.
2. The migrate Job needs **both** `ASTRA_DATABASE_URL` *and* `ASTRA_JWT_SECRET_KEY`.
   `alembic/env.py` calls `get_settings()`, which validates the whole Settings model — with
   only the URL it fails with `jwt_secret_key: Field required`.

`.gcloudignore` keeps `.venv/`, tests and caches out of the build context — but deliberately
**keeps `downloads/*.zip`**, which the backend serves as the agent bundles.

---

## 5. Data copy — Railway → Neon (`astra-dbcopy` job)

No local `pg_dump` needed: the copy runs as a Cloud Run Job from a `postgres:18-alpine`
image, so both URLs stay in Secret Manager and never touch a workstation.

- `MIGRATE_SRC_URL` — Railway's **public proxy** URL (`…proxy.rlwy.net`). Only ever READ.
  Railway's `.railway.internal` host is unreachable from GCP; the script asserts against it.
- `MIGRATE_DST_URL` — Neon's **DIRECT** endpoint (no `-pooler`). `pg_restore` needs
  session-level operations that PgBouncer's transaction pooling doesn't support; `copy.sh`
  refuses a pooled URL outright.

```bash
gcloud run jobs execute astra-dbcopy --region asia-southeast1 --wait
```

The job dumps, restores with `--clean --if-exists` (full replace of the destination), then
prints row counts. First run result:

```
alembic_version=0034   organizations=11  users=13  devices=16
assets=5  remediation_tasks=49  audit_logs=557  telemetry_snapshots=25229   (dump 1.6M)
```

**Keeping the standby fresh:** Railway keeps taking writes, so Neon drifts. Re-run this job
whenever you want to refresh (it's a full, idempotent replace). At cutover, run it once more
so nothing is lost. For a truly seconds-long window, set up logical replication instead —
only worth it once the dump takes more than a minute or two.

### Verifying the destination (`astra-dbcheck`)

The same image carries `check.sh`, a read-only report (schema version, row counts, rollup
coverage):
```bash
gcloud run jobs execute astra-dbcheck --region asia-southeast1 --wait
# then read the output:
gcloud logging read 'resource.labels.job_name="astra-dbcheck"' --limit 40 \
  --format='value(textPayload)' --freshness=10m
```

⚠️ **Run these `gcloud` commands from PowerShell, not Git Bash.** Git Bash (MSYS) rewrites
POSIX-looking arguments into Windows paths — `--args /check.sh` silently became
`C:/Program Files/Git/check.sh`, which is what "Application exec likely failed" meant.
`MSYS_NO_PATHCONV=1` is not a fix here: it breaks gcloud's own launcher. Also note gcloud
splits `--args` on commas, so SQL with commas can't be passed inline — that's why the query
lives in `check.sh` rather than on the command line.

After the hardening deploy, this confirmed the 0035 backfill preserved everything:
```
alembic_version = 0035
telemetry_snapshots = 25229 | telemetry_rollups = 48
rollup_rows 48 | devices_covered 13 | 2026-07-11 → 2026-07-30 | snapshots_aggregated 25229
```
All 25 229 existing snapshots are represented in the rollups, so pruning can now only drop
rows whose history has already been captured.

---

## 6. Verifying the standby

```bash
URL=https://astra-backend-fmuizr4sda-as.a.run.app
curl $URL/health
# → {"status":"ok","email_enabled":true,"ai_enabled":true}   ← proves Resend + Anthropic secrets

curl -o /dev/null -w '%{http_code}\n' $URL/api/v1/devices/paged        # 401 = auth gate live
curl -X POST $URL/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"probe@gmail.com","password":"wrong"}'                   # 401 = DB readable
```
A 401 on the login probe (not a 500) is the real signal: the app reached Neon through the
pooled connection and queried `users`. Measured ~0.5 s.

Also worth a look before flipping: log in to the standby with a real admin and check
Devices / Compliance / Fleet Issues render the migrated data.

---

## 7. The flip (cutover)

1. A day before: **lower the DNS TTL** on `api.astra.technomateai.com` to 60 s.
2. `./deploy/cloudrun-deploy.sh` — standby on the latest image.
3. `gcloud run jobs execute astra-dbcopy --region asia-southeast1 --wait` — final data sync.
4. Map the domain and switch DNS as instructed:
   ```bash
   gcloud run domain-mappings create --service astra-backend \
     --domain api.astra.technomateai.com --region asia-southeast1
   ```
5. Watch agents come back Online; verify portal, auto-update, and a PayPal webhook.
6. Leave Railway **stopped-but-recoverable for a week** as rollback insurance.

**Rollback:** repoint the DNS record back at Railway. Nothing on any device changes.

---

## 8. Impact on the running environment

| Area | Impact | Why / mitigation |
|---|---|---|
| **Installed agents** | **None** | Same domain; they can't tell the backend moved. |
| **Heartbeats during cutover** | ~1–5 min gap → briefly **Offline**, then auto-recover | Agents have an offline queue; buffered telemetry resyncs. No data loss. |
| **Pending remediations** | Wait during the window, then deliver | Pull model — agents re-poll after cutover. |
| **Portal (Vercel)** | **None** | Domain unchanged ⇒ `NEXT_PUBLIC_API_URL` unchanged. |
| **Logged-in sessions** | **None** | `ASTRA_JWT_SECRET_KEY` is reused. |
| **Enrollment keys / distributed installers** | **None** | Keys live in the DB (copied); domain unchanged. |
| **Auto-update** | **None** | Manifest is served from GitHub releases; signing key stays in GitHub Actions. |
| **PayPal webhooks** | **None** | Same webhook URL. |
| **Writes in the final seconds** | Could be missed | Run the final `astra-dbcopy` in a low-traffic window. |
| **Total user-visible downtime** | **A few minutes** | Low DNS TTL + a 1.6 MB dump keep it short. |

---

## 9. Cost

- **Cloud Run** `min-instances 1`: a few $/mo idle + usage.
- **Neon**: free tier today; ~$19+/mo for PITR/production retention — **enable this before
  the flip**, since PITR is the main data-safety reason for moving.
- No Redis or Qdrant spend (unused).

Ballpark **~$25–50/mo** at current scale.

---

## 10. Hardening — **done** (migration 0035)

All three landed before the flip, so the standby and Railway run the same hardened code.

1. **Connection pool + `pool_pre_ping`.** Pool settings are now env-driven
   (`ASTRA_DB_POOL_SIZE`, `ASTRA_DB_MAX_OVERFLOW`, `ASTRA_DB_POOL_RECYCLE_SECONDS`), and
   **`pool_pre_ping` is on** — *required* on Neon, which scales compute to zero after ~5
   min idle and restarts weekly for updates. Without it the first request after either
   event gets a dead pooled connection and fails. Total connections against Postgres are
   `(pool + overflow) × instances`, which is why this is configurable per platform.
2. **Telemetry retention + daily rollups.** New `telemetry_daily_rollups` table
   (1 row/device/day: avg+max CPU, avg+max RAM, worst disk-free %) is written on every
   ingest, *then* raw snapshots older than `ASTRA_TELEMETRY_RETENTION_DAYS` (7) are pruned
   **for that device only** — no cron, work per ingest stays constant as the fleet grows.
   Rollups are never pruned, so pruning doesn't destroy history.
   A **floor** (`ASTRA_TELEMETRY_KEEP_MIN_SNAPSHOTS`, 60) keeps a device's newest rows
   whatever their age: a device returning from weeks offline flushes its offline queue with
   stale `collected_at` values, and pruning purely by age would delete all of them on
   arrival — leaving it with no telemetry at all and an "unknown" disk compliance check.
3. **Agent rate limiting — log-only.** Per-**device** fixed window (120 req/60 s vs a
   healthy agent's ~6/min, so it only catches a stuck retry loop). Keyed by device id, not
   IP, so one bad agent can't affect an office behind the same NAT. Breaches are logged and
   **allowed**; flip `ASTRA_AGENT_RATE_LIMIT_ENFORCE=true` only after watching real fleet
   traffic — a tight limit would drop genuine heartbeats and show devices offline. The
   counter is in-process (no Redis here), so on Cloud Run the effective ceiling is
   `limit × instances`.

---

## 11. Cutover checklist

- [x] Neon created (Singapore), pooled + direct URLs
- [x] 11 secrets in Secret Manager; runtime SA granted access
- [x] Artifact Registry repo + image built via Cloud Build
- [x] `astra-migrate` run against Neon → `alembic head` (0034)
- [x] Cloud Run deployed and smoke-tested on `*.run.app`
- [x] `astra-dbcopy` run → production data in Neon
- [ ] Neon paid tier / PITR enabled
- [ ] Hardening (§10)
- [ ] DNS TTL lowered to 60 s
- [ ] Final `astra-dbcopy` in the cutover window
- [ ] Domain mapped → `api.astra.technomateai.com` → Cloud Run
- [ ] Verified: health, portal, agent heartbeat, auto-update, webhook
- [ ] Railway left stopped-but-recoverable for 1 week
