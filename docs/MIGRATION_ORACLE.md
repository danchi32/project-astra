# ASTRA on Oracle Cloud — migration and autoscaling plan

Status: **plan, not started.** Written 2026-10-28.

Moves the ASTRA backend off Google Cloud Run + Neon onto Oracle Cloud Infrastructure (OCI),
in three phases that follow device count. The portal stays on Vercel. The agent, its
installer and its release pipeline do not change.

The goal is lower hosting cost **with no loss of speed**. Every phase therefore has an
explicit trigger to move to the next one before the current one runs out of headroom.

---

## 1. Facts this plan rests on

Everything below was measured or read on 2026-10-28. Re-check the prices before spending.

### 1.1 What runs today

| Piece | Where | Notes |
|---|---|---|
| Backend API | Cloud Run `astra-backend`, Singapore | min 1, max 20 instances |
| Remote-control listener | Cloud Run `astra-remote-listener` | min 1, **max 1**, CPU always on |
| Marketing service | Cloud Run `astra-marketing` | own database (`ASTRA_MKT_DATABASE_URL`) |
| Staging | Cloud Run `astra-backend-staging` | min 0; `astra_staging` DB on the same Neon project |
| MeshCentral relay | GCE VM `astra-relay`, e2-small, 20 GB | ports 80 and 443 only |
| Database | Neon Postgres, Singapore | prod, staging, marketing |
| One-off jobs | Cloud Run Jobs | migrate, seed, restore drill, etc. |
| Portal | Vercel | **not moving** |

Agents do **not** pin the backend IP (`ASTRA_AGENT_BACKEND_IP` is empty in prod), and the
installer has `https://api.astra.technomateai.com` compiled in. So a DNS change moves every
agent to the new server, with no reinstall and no installer rebuild.

### 1.2 Latency (from the developer's PC in India)

| Path | Time |
|---|---|
| Current API: Google edge connect | 25–50 ms |
| Current API: edge → Singapore → response | ~85–90 ms on top |
| OCI Mumbai (`ap-mumbai-1`), TCP connect | **~50 ms** |
| OCI Hyderabad (`ap-hyderabad-1`) | ~80–90 ms |
| OCI Singapore (`ap-singapore-1`) | ~100 ms |
| Prod `/agent/telemetry` server time (last hour) | p50 49 ms, p95 98 ms |

**Home region: Hyderabad** (`ap-hyderabad-1`). The account was created there on 2026-10-29,
and the home region cannot be changed; Always Free compute exists only in the home region.
From the developer's PC that means network latency about the same as today (~80–90 ms vs
~85–90 ms), not Mumbai's ~50 ms. The server-side gains (local database, no Neon cold start)
still apply, and devices in south India will be closer to Hyderabad than this measurement.

### 1.3 Oracle Always Free (from oracle.com/in/cloud/free)

| Resource | Free amount |
|---|---|
| Arm Ampere A1 | 1,500 OCPU-hours + 9,000 GB-hours/month ≈ **2 OCPU + 12 GB** always on, as 1 or 2 VMs |
| AMD micro VMs | 2 × (1/8 OCPU, 1 GB) — too small for the backend |
| Block storage | 200 GB total, 2 volumes, 5 backups |
| Object storage | 20 GB, 50k API requests/month |
| Outbound data | 10 TB/month |
| Load balancer | 1 flexible LB at 10 Mbps; 1 network LB |
| Vault | 150 secrets |
| Monitoring / Logging / Notifications | free tiers (Logging 10 GB/month) |
| Databases | Autonomous DB (Oracle), NoSQL, HeatWave (MySQL). **No PostgreSQL.** |

ASTRA is PostgreSQL-only (`asyncpg`, 118 `postgresql.UUID` columns, JSONB). Moving to Oracle
DB or MySQL would be a rewrite, so Postgres runs on our own VM (or OCI's paid managed
PostgreSQL in Phase 3).

### 1.4 Oracle paid rates (from oracle.com/cloud/price-list)

| Item | Rate |
|---|---|
| Arm A1 OCPU (1 OCPU = 1 vCPU) | $0.01 / OCPU-hour |
| Arm A1 memory | $0.0015 / GB-hour |
| Block volume, balanced (storage $0.0255 + 10 VPU × $0.0017) | ~$0.0425 / GB-month |
| Object storage | $0.0255 / GB-month |
| Flexible load balancer | $0.0113 / hour + $0.0001 per Mbps-hour |
| Kubernetes Engine (OKE) | Basic cluster free; Enhanced $0.10 / cluster-hour |
| OCI Database with PostgreSQL (x86, 1 OCPU = 2 vCPU) | $0.098 / OCPU-hour, **plus storage (not priced here)** |

Paid usage is billed only above the Always Free amounts.

### 1.5 Load per device

From `docs/COST_MODEL_2K_DEVICES.md`: today's agent makes **4 requests/minute/device**
(heartbeat 60 s, telemetry 60 s, tray task poll 30 s). That model sizes 2,000 devices at
~8 vCPU of API (instance-billed Cloud Run, "agent as-is") and roughly double the optimised
database load. This plan assumes, **per 1,000 devices with today's agent**:

| Tier | CPU | Memory | Storage |
|---|---|---|---|
| API | 4 vCPU | 8 GB | — |
| Postgres | 3 vCPU | 12–16 GB | ~75 GB |

These are planning numbers, not a load test. **Section 7 replaces them with measured ones
before Phase 2 is built.** With the optimised agent (2 requests/minute) every figure roughly
halves.

---

## 2. Cost comparison (hosting only, per month)

Covers compute, database, storage, load balancer, egress, logging, CI/registry and backups.
AI inference, Vercel, Resend, Sentry, code signing and DNS cost the same on either cloud
and are left out. ₹ at ₹88/$.

| Devices | GCP + Neon (today's design) | **OCI, self-managed Postgres** | OCI + managed PostgreSQL |
|---|---|---|---|
| ≤ 150–200 | today's bill (Neon was ~$18) | **$0** (Phase 1, Always Free) | — |
| 500 | $230–460 | **~$50–60** | not worth it yet |
| 1,000 | $455–930 | **~$85–100** | ~$195 + storage |
| 2,000 | $910–1,855 | **~$195–210** | ~$330 + storage |
| 3,000 | $1,365–2,785 (₹1.2–2.45 L) | **~$295–310 (₹26–27 k)** | ~$530 + storage |

GCP + Neon figures are the hosting lines of `COST_MODEL_2K_DEVICES.md` scenario A, scaled
linearly. Oracle figures are built bottom-up in section 6.

**Conclusion: OCI is roughly 5–9× cheaper to host at every size from 500 to 3,000 devices.**
The saving pays for part-time DevOps time from about 1,000 devices up. That DevOps
responsibility is the real price of the move (section 8).

---

## 3. Phase 1 — one free VM (now → ~150–200 devices) · $0/month

### 3.1 Shape

One `VM.Standard.A1.Flex`, **2 OCPU / 12 GB**, Ubuntu 24.04 (aarch64), Hyderabad:

- Boot volume 100 GB, plus one 100 GB block volume mounted at `/var/lib/postgresql`
  (separate volume = independent backups; total stays within the free 200 GB).
- Docker Compose stack:

| Container | Role |
|---|---|
| `caddy` | HTTPS (automatic Let's Encrypt) for the API and relay hostnames |
| `backend` | FastAPI / uvicorn, 2 workers |
| `listener` | `scripts/remote_control_listener.py`, exactly one |
| `marketing` | marketing service |
| `postgres:16` | prod DB + marketing DB; **not** published on a host port |
| `meshcentral` | relay, with its existing `meshcentral-data` |

Staging is **not** always on (12 GB is the whole budget). Run it on demand as a second
compose project with its own database, and stop it afterwards.

### 3.2 Account setup

1. Sign up for Free Tier (done 2026-10-29, home region **Hyderabad**).
2. **Upgrade to Pay As You Go** straight away. It stays $0 inside the free amounts, and
   avoids Oracle reclaiming "idle" Always Free instances on free accounts (ASTRA's low CPU
   would look idle). Confirm the current reclamation policy in Oracle's docs.
3. Budget with an alert at ₹100, so any accidental paid resource is caught the same day.
4. If A1 says "out of host capacity", retry later or in another availability domain.

### 3.3 Hardening (CLAUDE.md security requirements)

- HTTPS only (Caddy); HTTP redirects.
- SSH by key only, password login off; security list opens 22 (ideally to your IP or
  through OCI Bastion, free), 80 and 443. **Do not copy GCP's open RDP rule.**
- Oracle's Ubuntu images ship an `iptables` REJECT rule: open 80/443 there too, or the
  security list change appears not to work.
- Postgres and the containers' internal ports never published to the internet.
- Block volumes are encrypted at rest by OCI by default.
- Secrets in OCI Vault (free), rendered to a root-only `0600` env file at deploy.
- `unattended-upgrades` for OS security patches.

### 3.4 Backups

- Nightly `pg_dump` (prod + marketing) → Object Storage, 7 days kept (fits the free 20 GB
  while the DB is small).
- Weekly block-volume backup of the Postgres volume (5 free).
- Monthly restore drill, reusing the existing restore-drill approach (dump, restore into a
  scratch database, compare row counts, drop).

### 3.5 CI/CD

- GitHub Actions builds **arm64** images with `docker buildx --platform linux/arm64` and
  pushes to GitHub Container Registry (or OCI Registry).
- Deploy over SSH: run `alembic upgrade head`, then `docker compose pull && up -d`, then
  the same `/health` gate the Cloud Run workflow uses.
- `deploy-backend.yml` and `deploy-staging.yml` are replaced. `agent-release.yml` is
  unchanged (it publishes to GitHub Releases).
- The listener is deployed by the same compose file. The Cloud Run listener step added in
  PR #39 goes away with Cloud Run.

### 3.6 Monitoring

- OCI Monitoring alarms → Notifications (email): CPU > 60% for 15 min, memory > 80%,
  disk > 80%, instance down.
- External `/health` check every few minutes (OCI APM Synthetic Monitoring, free tier).

### 3.7 Move to Phase 2 when any of these is true

- ~150 active devices,
- CPU above 60% for an hour on a normal day,
- `/agent/telemetry` p95 above **200 ms** (today: 98 ms).

---

## 4. Phase 2 — split tiers, API autoscaling (~200 → ~1,000 devices)

### 4.1 Shape

```
                 Flexible Load Balancer (TLS)
                            │
              ┌─────────────┴─────────────┐
        API instance pool (A1, autoscaled, min 2)
              └─────────────┬─────────────┘
                            │ private subnet
          ┌─────────────────┼──────────────────┐
     Postgres VM        Redis (small)     Relay VM: MeshCentral + listener
   (A1, PgBouncer)                         (single instance each)
```

- **API**: OCI *instance configuration* (A1, 1–2 OCPU, 4 GB, cloud-init pulls the image)
  + *instance pool* + *autoscaling configuration*:
  - scale out +1 when pool CPU > 60% for 5 min, scale in −1 when < 30%;
  - minimum **2** (one can fail or be redeployed without downtime), maximum sized to budget;
  - LB health check on `/health`.
  - Deploy = new instance configuration with the new image tag, then a rolling replace.
- **Postgres**: its own A1 VM, data on a block volume, **PgBouncer** in front. With several
  API instances × workers, each with a pool of 5 + 10 overflow, raw connections would
  exceed Postgres's limit without it.
- **Relay VM**: MeshCentral and the listener. Both must run as exactly one instance; they
  are never in the autoscaled pool.
- **Redis**: small, on the relay or DB VM (see 4.2).

### 4.2 Code changes required before Phase 2

| Change | Why |
|---|---|
| Move the refused-device cache (`services/subscription.py`) to Redis | It is per process. With several API instances, an org that upgrades can be refused by other instances for up to the 12-hour TTL. Its `ponytail:` note already names Redis as the upgrade path. |
| Move the agent rate limiter to Redis, or accept per-instance limits | Same per-process limitation. |
| Confirm nothing else assumes one API process | e.g. the AI classifier debounce (`workforce_ai._last_run`) is per process; harmless, but re-check. |

### 4.3 Move to Phase 3 when

- ~1,000 devices, or Postgres CPU above 60% sustained,
- or the business needs managed database failover / point-in-time recovery.

---

## 5. Phase 3 — scale and resilience (~1,000 → 3,000+ devices)

Two acceptable paths for the API; pick based on who runs operations.

| | Keep instance pools (Phase 2) | Kubernetes (OKE) |
|---|---|---|
| Control plane cost | none | Basic free; Enhanced $73/month |
| Autoscaling | pool CPU rules | HPA (pods) + cluster autoscaler (nodes) |
| Deploys | rolling instance replace | rolling pods, fast rollback |
| Operational skill needed | lower | higher |
| Recommendation | **default** | when there are several services or a dedicated DevOps engineer |

Database at this size:

- **Self-managed**: larger A1 VM + streaming replica on a second VM + continuous WAL
  archiving to Object Storage (point-in-time recovery). Cheapest; you own failover.
- **OCI Database with PostgreSQL** (managed): ~$0.098/OCPU-hour plus storage. Adds roughly
  $130–230/month plus storage at 2,000–3,000 devices over self-managed. Buys managed backups
  and failover.

**Postgres does not autoscale.** Growing it means resizing the VM (a reboot, so a short
planned window) or moving to the managed service. Plan DB growth a step ahead of need.

---

## 6. How the Oracle figures were built

Rates from 1.4; 730 hours/month; Always Free amounts (1,500 OCPU-h, 9,000 GB-h, 200 GB block,
20 GB object) deducted once. API sized at average load; autoscaling peaks add roughly
$15–30/month on top.

| Devices | API pool | Postgres | Relay + listener | Total CPU / RAM | Compute | Block | LB | Logs + backups | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| 500 | 2 × (1 OCPU, 4 GB) | 2 OCPU, 12 GB | 1 OCPU, 4 GB | 5 OCPU / 24 GB | $34 | $2 | $12 (50 Mbps) | $0–10 | **~$50–60** |
| 1,000 | 4 OCPU, 8 GB | 3 OCPU, 16 GB | 1 OCPU, 4 GB | 8 OCPU / 28 GB | $61 | $3 | $16 (100 Mbps) | $5–17 | **~$85–100** |
| 2,000 | 8 OCPU, 16 GB | 6 OCPU, 32 GB | 2 OCPU, 6 GB | 16 OCPU / 54 GB | $147 | $11 | $23 (200 Mbps) | $15–25 | **~$195–210** |
| 3,000 | 12 OCPU, 24 GB | 9 OCPU, 48 GB | 2 OCPU, 6 GB | 23 OCPU / 78 GB | $225 | $18 | $30 (300 Mbps) | $22–37 | **~$295–310** |

Example, 3,000 devices: CPU (23 × 730 − 1,500) × $0.01 = $153; memory (78 × 730 − 9,000) ×
$0.0015 = $72; block (8 boot volumes × 50 GB — 6 API, 1 Postgres, 1 relay — + 225 GB data
− 200 GB free) × $0.0425 = $18.

Managed PostgreSQL column (section 2): the self-managed Postgres VM and its data volume are
swapped for OCI Database with PostgreSQL at half the vCPU count in x86 OCPUs (rounded up),
storage excluded: 1,000 → 2 OCPU ($143), 2,000 → 3 OCPU ($215), 3,000 → 5 OCPU ($358).

Outbound data stays inside the free 10 TB at every size here (the cost model puts 2,000
devices at 120–400 GB/month).

---

## 7. Before building Phase 2: measure, don't trust section 1.5

A load test on a Phase-1-sized VM, with simulated agents at today's request mix (heartbeat,
telemetry with realistic payloads, tray poll), at 150, 300 and 500 devices. Record API p95,
Postgres CPU, connections and disk growth per device per day. Then:

- replace the per-1,000-device sizing in 1.5 with the measured one,
- recompute section 6,
- set the autoscaling maximum and the Phase 3 trigger from real numbers.

---

## 8. Risks and what we give up

| Risk | Mitigation |
|---|---|
| We now run the servers: OS patches, Postgres upkeep, backups, on-call | Automate patches and backups; monthly restore drill; alarms to email; budget DevOps time from ~1,000 devices |
| Single VM in Phase 1 = single point of failure | Accept while small; Phase 2 removes it for the API, Phase 3 for the DB |
| No autoscaling for Postgres | Resize ahead of need (section 5) |
| A1 capacity may be unavailable when we need to scale | PAYG account; capacity reservations once paid usage is steady |
| arm64 images | `python:3.11-slim` is multi-arch; `asyncpg`, `pydantic-core`, `cryptography` ship aarch64 wheels. Verify the full build in CI before cutover. |
| MeshCentral agents stop trusting a new relay | Move `meshcentral-data` (certificates) as-is and keep the same relay hostname |
| Rollback after cutover loses writes made on OCI | Short cutover window; rollback decision within the first hours |
| Neon → own Postgres loses Neon's managed branching/restore | Phase 1 backups + monthly drill; Phase 3 WAL archiving or managed PostgreSQL |

---

## 9. Cutover runbook (Phase 1)

1. **T−1 day**: lower DNS TTL to 60 s on `api.astra.technomateai.com` and the relay hostname.
2. Build the OCI VM, stack, secrets and backups. Restore a **copy** of prod into it and test
   on a temporary hostname: login, device list, agent enrol, heartbeat, telemetry, remote
   session, PayPal webhook (test mode), email.
3. **Window (~30 min)**:
   1. Put the API in maintenance (stop Cloud Run traffic); stop the GCP relay.
   2. Final `pg_dump` of prod and marketing from Neon → restore on OCI; check
      `alembic current` is head; compare row counts.
   3. Copy `meshcentral-data` and `meshcentral-files` to the OCI relay; start it.
   4. Switch DNS for the API and relay hostnames to the OCI IP.
4. **Verify**: `/health`; agent requests returning 200 (and 403 for expired orgs); portal
   login; a remote-control session end to end; a payment webhook.
5. **Keep GCP + Neon untouched for 7 days** as rollback (switch DNS back).
6. **Decommission**: Cloud Run services and jobs, the `astra-relay` VM, GCP Secret Manager
   entries, Artifact Registry images, the Neon project. Update the restore-drill doc and
   `docs/MIGRATION_CLOUDRUN_NEON.md` to point here.
