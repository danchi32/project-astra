# ASTRA Backend Migration Runbook — Railway → Google Cloud Run + Neon

Move the FastAPI backend off Railway to **Cloud Run** (compute) + **Neon** (Postgres) +
**Upstash** (Redis) + **Qdrant Cloud** (vectors), in the **Mumbai** region (`asia-south1`),
with **near‑zero impact** on already‑enrolled agents.

> The portal stays on **Vercel** — nothing to migrate there. Only its
> `NEXT_PUBLIC_API_URL` may change (and even that is avoidable, see the Golden Rule).

---

## 0. Golden rule — keep the domain, and the agents never notice

Every installed agent (and every installer we ever handed out) has the backend URL
**baked in** (`public_api_url`, e.g. `https://api.technomateai.com`). The auto‑update
manifest and enrollment all resolve through that host.

**So: keep the same custom domain.** We point `api.technomateai.com` at Cloud Run instead
of Railway. The agents keep calling the exact same URL — **no re‑install, no config push,
no agent release**. Migration becomes "swap what's behind the domain."

If you do *not* keep the domain, every device must be re‑pointed (a reinstall) — avoid this.

---

## 1. Target architecture

```
Windows Agents ─┐
                ├─ https://api.technomateai.com ─→ Cloud Run (FastAPI, asia-south1, min=1)
Vercel Portal ──┘                                    │
                                                     ├─→ Neon Postgres   (asia-south1, PITR on)
                                                     ├─→ Upstash Redis   (Mumbai/global)
                                                     └─→ Qdrant Cloud    (or self-host)
Secrets ─→ Google Secret Manager
Container image ─→ Google Artifact Registry
```

---

## 2. Prerequisites (one-time)

- A **Google Cloud** project with billing enabled; `gcloud` CLI installed + `gcloud init`.
- A **Neon** account, an **Upstash** account, a **Qdrant Cloud** account.
- Access to the **DNS** for `technomateai.com` (to repoint the API host).
- The current **Railway env vars** (copy them out — you'll re-enter the secret values
  yourself into Secret Manager; do not paste secrets into this doc or into git).

Enable the Google APIs:
```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com
gcloud config set run/region asia-south1
```

---

## 3. Environment variable inventory (from `app/core/config.py`)

Move **all** of these. Values you set yourself in Secret Manager / Cloud Run — never in git.

**Required**
- `DATABASE_URL` → the Neon connection string (see Step 4). Must be an **async** URL:
  `postgresql+asyncpg://USER:PASSWORD@HOST/DB?ssl=require`
- `JWT_SECRET_KEY` → reuse the SAME value as Railway (so existing refresh tokens stay valid;
  a new value logs everyone out — acceptable, but reuse to avoid it).
- `PUBLIC_API_URL` → `https://api.technomateai.com` (unchanged).
- `PUBLIC_APP_URL` → `https://astra.technomateai.com` (unchanged).
- `CORS_ORIGINS` → include the portal origin.

**Infra**
- Redis (Upstash) — whatever your config key is (`REDIS_URL`).
- Qdrant — host/api key (`QDRANT_URL`, `QDRANT_API_KEY`).
- `AGENT_BACKEND_IP` → keep **empty** (custom domain resolves; no host-pin needed).

**Auto-update (unchanged — served through the same domain)**
- `AGENT_UPDATE_MANIFEST_URL`, `AGENT_UPDATE_SIGNATURE_URL`
  (the RSA **signing private key** lives only in GitHub Actions — nothing to migrate here).

**Email** — `RESEND_API_KEY` or `SMTP_HOST/PORT/USER/PASSWORD`, `EMAIL_FROM`.

**Billing** — `RAZORPAY_KEY_ID/SECRET/PLAN_ID/WEBHOOK_SECRET`, `PADDLE_*` (and update the
webhook URLs in the Razorpay/Paddle dashboards to the new domain — but since the domain is
unchanged, **webhooks keep working**).

**AI** — the model provider key(s).

---

## 4. Neon — the Postgres (do this first; it's the highest-stakes piece)

1. Create a Neon **project** in **`asia-south1` (Mumbai)**.
2. Create a database (e.g. `astra`).
3. **Enable Point-in-Time Recovery / history retention** on the paid tier (this is the
   whole reason we're moving — tested, restorable backups).
4. Copy the connection string; convert the driver to async for ASTRA:
   `postgresql+asyncpg://…?ssl=require`.
5. Keep it — it becomes `DATABASE_URL`.

---

## 5. Upstash (Redis) + Qdrant Cloud

- **Upstash**: create a Redis database in Mumbai/global → copy the URL → set as the Redis env.
- **Qdrant Cloud**: create the smallest cluster (or self-host on the Cloud Run image later) →
  copy host + API key. You'll re-index the knowledge base (small) after cutover, or snapshot
  (Step 8).

---

## 6. Secret Manager (so secrets never sit in the service config)

For each secret value:
```bash
printf '%s' 'THE_VALUE' | gcloud secrets create JWT_SECRET_KEY --data-file=-
# repeat for DATABASE_URL, REDIS_URL, QDRANT_API_KEY, RAZORPAY_*, RESEND_API_KEY, ...
```
Grant the Cloud Run runtime service account access:
```bash
gcloud secrets add-iam-policy-binding JWT_SECRET_KEY \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 7. Build & push the image (Artifact Registry)

The backend is already Dockerized — no code changes needed.
```bash
gcloud artifacts repositories create astra --repository-format=docker --location=asia-south1
gcloud auth configure-docker asia-south1-docker.pkg.dev

# from backend/
IMAGE=asia-south1-docker.pkg.dev/PROJECT_ID/astra/backend:$(git rev-parse --short HEAD)
docker build -t "$IMAGE" .
docker push "$IMAGE"
```

---

## 8. Migrations — run them as a JOB, not per-instance

`entrypoint.sh` currently runs `alembic upgrade head` on start. On Cloud Run several
instances can cold‑start at once and race on the migration. **Run migrations once, as a
separate step, before routing traffic:**

```bash
gcloud run jobs create astra-migrate --image "$IMAGE" --region asia-south1 \
  --set-secrets DATABASE_URL=DATABASE_URL:latest \
  --command alembic --args upgrade,head
gcloud run jobs execute astra-migrate --wait
```
(For the long term, drop the `alembic upgrade head` line from `entrypoint.sh` and always
migrate via this job in the deploy pipeline.)

---

## 9. Data migration (Railway Postgres → Neon)

Small DB ⇒ a short dump/restore. Do the **final** dump inside the maintenance window (Step 10).

```bash
# Dump from Railway (get the Railway PG URL from its dashboard)
pg_dump --no-owner --no-privileges --format=custom \
  "postgresql://USER:PASS@RAILWAY_HOST:PORT/railway" -f astra.dump

# Restore into Neon (plain psql URL, not the +asyncpg one)
pg_restore --no-owner --no-privileges --clean --if-exists \
  -d "postgresql://USER:PASS@NEON_HOST/astra?sslmode=require" astra.dump
```
Enrollment keys, users, devices, telemetry, audit logs — all travel with this dump.

**Qdrant**: either re-index the knowledge base from the DB after cutover (it's rebuildable),
or take a Qdrant snapshot and restore into Qdrant Cloud.

---

## 10. Cutover (the only window with any disruption)

Keep it short (minutes). Do it in low-traffic hours.

1. **Deploy the Cloud Run service** (pointing at Neon/Upstash/Qdrant), but don't send the
   domain yet:
   ```bash
   gcloud run deploy astra-backend --image "$IMAGE" --region asia-south1 \
     --min-instances 1 --max-instances 10 --concurrency 80 --port 8000 \
     --allow-unauthenticated \
     --set-secrets DATABASE_URL=DATABASE_URL:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest,REDIS_URL=REDIS_URL:latest \
     --set-env-vars PUBLIC_API_URL=https://api.technomateai.com,PUBLIC_APP_URL=https://astra.technomateai.com
   ```
   `--min-instances 1` = no cold starts and any background loop stays alive.
2. **Freeze writes briefly** on Railway (or just accept a few minutes where the last
   writes are re-dumped): run the **final** `pg_dump`/`pg_restore` (Step 9) so Neon is current.
3. **Smoke-test Cloud Run** on its `*.run.app` URL: `/health`, admin login, one device call.
4. **Repoint DNS**: map `api.technomateai.com` to Cloud Run:
   ```bash
   gcloud run domain-mappings create --service astra-backend \
     --domain api.technomateai.com --region asia-south1
   ```
   Update the DNS record as instructed. **Lower the DNS TTL to 60s a day before** so the
   switch propagates fast.
5. Once DNS points to Cloud Run and health is green, **decommission Railway** (keep it
   stopped-but-recoverable for a week as rollback insurance).

---

## 11. Verify

- `curl https://api.technomateai.com/health` → ok, and it's hitting Cloud Run (check logs).
- Portal: login, Devices list, Compliance, Fleet Issues, push a fix.
- An **agent**: within ~1–2 min a heartbeat lands (device flips back to Online).
- Auto-update manifest still served: an agent update check succeeds.
- A billing webhook test fires (same domain → still valid).

---

## 12. Rollback

Because the domain is the switch: if anything is wrong, **repoint `api.technomateai.com`
back to Railway** (DNS) and Railway (still running, DB intact) serves again. That's why we
keep Railway stopped-but-recoverable for a week. No agent touch needed either way.

---

## 13. Impact on the running environment — "kya effect padega"

| Area | Impact | Why / mitigation |
|---|---|---|
| **Installed agents** | **None** (if domain kept) | Same `api.technomateai.com`; agents don't know the backend moved. |
| **Agent heartbeats during cutover** | ~1–5 min gap → devices briefly show **Offline**, then auto-recover | Agents have an **offline queue** — buffered telemetry resyncs. No data loss. |
| **Windows Update / remediation pushes** | Any pending task waits during the window, then delivers | Pull model — agents re-poll after cutover. |
| **Portal (Vercel)** | Only if `NEXT_PUBLIC_API_URL` changed | Keep the domain ⇒ no portal change. Else update the env var + redeploy. |
| **Logged-in users' sessions** | **None** if `JWT_SECRET_KEY` reused; else everyone re-logs-in | Reuse the same secret. |
| **Enrollment keys / installers already distributed** | **None** | Keys live in the DB (migrated); domain unchanged. |
| **Auto-update** | **None** | Manifest served from the same domain; signing key is in GitHub, untouched. |
| **Billing webhooks (Razorpay/Paddle)** | **None** | Same webhook URL (domain unchanged) ⇒ providers keep delivering. |
| **In-flight data at the exact switch** | The last few seconds of writes could be missed if not in the final dump | Freeze writes for the final dump, or run in low-traffic window. |
| **Total user-visible downtime** | **A few minutes** (DNS + final sync), scoped to the cutover | Low-TTL DNS + small DB keep it short. |

**Net:** with the domain kept, this is a low-drama migration — a short cutover window,
agents self-heal via their offline queue, and rollback is a single DNS flip.

---

## 14. Rough monthly cost (low → growing scale)

- Cloud Run: pay-per-use; `min-instances 1` ≈ a few $/mo idle + usage.
- Neon: free tier for early, ~$19+/mo for PITR/production.
- Upstash: pay-per-request (often ~$0–5 early).
- Qdrant Cloud: smallest tier or self-host free.

Ballpark **~$25–50/mo** early — comparable to Railway, but with real PITR data safety and
autoscaling headroom.

---

## 15. Cutover checklist

- [ ] Neon created (Mumbai, PITR on), `DATABASE_URL` (asyncpg) ready
- [ ] Upstash + Qdrant Cloud created
- [ ] Secrets in Secret Manager; runtime SA granted access
- [ ] Image built + pushed to Artifact Registry
- [ ] `astra-migrate` job run against Neon → `alembic head`
- [ ] Cloud Run deployed, smoke-tested on `*.run.app`
- [ ] DNS TTL lowered to 60s (day before)
- [ ] Final `pg_dump`/`pg_restore` in the window
- [ ] Domain mapped → `api.technomateai.com` → Cloud Run
- [ ] Verified: health, portal, agent heartbeat, auto-update, webhook
- [ ] Railway left stopped-but-recoverable for 1 week (rollback)
