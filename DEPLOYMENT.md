# Deploying ASTRA

Three pieces deploy independently:

| Piece | Where | How |
|---|---|---|
| **Portal** (Next.js) | Vercel | Git import, root dir `portal` |
| **Backend** (FastAPI) | Render + managed Postgres | `render.yaml` blueprint |
| **Agent installer** (`.exe`) | GitHub Release | CI on a `agent-v*` tag |

> Vercel is serverless and cannot run the FastAPI backend or its database — that's
> why the backend lives on Render. Redis and Qdrant from `infra/` are **not** needed
> by the current backend (the semantic cache lives in Postgres); add them only when
> the vector knowledge base is switched on.

---

## 1. Backend → Render

1. In Render: **New → Blueprint**, point it at this repo. It reads `render.yaml` and
   provisions a Dockerized web service (`backend/Dockerfile`) plus a free Postgres.
2. Set the env vars marked `sync: false` on the `astra-backend` service:
   - `ASTRA_CORS_ORIGINS` — your Vercel URL as a JSON array, e.g. `["https://astra.vercel.app"]`
   - `ASTRA_PUBLIC_API_URL` — the backend's own public URL (fill in after the first deploy),
     e.g. `https://astra-backend.onrender.com`. Baked into the agent installer default.
   - `ASTRA_BOOTSTRAP_ADMIN_EMAIL` / `ASTRA_BOOTSTRAP_ADMIN_PASSWORD` (≥12 chars) /
     `ASTRA_BOOTSTRAP_ORG_NAME` — creates your first admin on the empty DB.
   - `ASTRA_ANTHROPIC_API_KEY` — optional; without it the deterministic stub AI is used.
   - `ASTRA_DATABASE_URL` and `ASTRA_JWT_SECRET_KEY` are wired automatically.
3. On deploy the container runs `entrypoint.sh`: `alembic upgrade head` → bootstrap admin →
   `uvicorn`. Health check: `GET /health`.

Log in once at the backend's `/docs` or via the portal with the bootstrap admin.

## 2. Portal → Vercel

1. In Vercel: **Add New → Project**, import this repo.
2. Set **Root Directory** to `portal`.
3. Add one environment variable:
   - `NEXT_PUBLIC_API_URL` = your Render backend URL (e.g. `https://astra-backend.onrender.com`)
   - (optional) `NEXT_PUBLIC_AGENT_DOWNLOAD_URL` = the installer release asset URL if your
     repo/owner differs from the default.
4. Deploy. The portal proxies `/api/*` to the backend via `next.config.ts` rewrites, so the
   browser stays same-origin (no CORS needed). After it's live, add that Vercel URL to the
   backend's `ASTRA_CORS_ORIGINS`.

## 3. Agent installer → GitHub Release

The installer `.exe` is built by CI (`.github/workflows/agent-installer.yml`) — no local
.NET SDK required.

```bash
git tag agent-v0.1.0
git push origin agent-v0.1.0
```

A Windows runner publishes the self-contained agent, compiles the Inno Setup installer, and
attaches `AstraAgentSetup.exe` to the release. The portal's **Devices → Install agent** links
to `releases/latest/download/AstraAgentSetup.exe`.

### Installing on an endpoint

- **From the portal**: Devices → Install agent → generate a token → download the `.exe` and run
  the shown silent command, or double-click and paste the token.
- **Silent / scripted**:
  ```
  AstraAgentSetup.exe /VERYSILENT /SERVERURL=https://astra-backend.onrender.com /TOKEN=<token>
  ```

The device enrolls on first start and appears under **Devices** within ~60s.

---

## Local development

Unchanged — see `infra/docker-compose.yml`, `backend/scripts/run_demo.py`, and
`portal` (`npm run dev`). The demo backend uses SQLite and a seeded admin.
