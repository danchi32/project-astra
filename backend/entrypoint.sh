#!/usr/bin/env bash
# Production startup: apply migrations, optionally seed the first admin, then serve.
set -euo pipefail

# On single-instance PaaS (Railway) migrations run here on start (default).
# On multi-instance Cloud Run, set RUN_MIGRATIONS_ON_START=false and run migrations
# once via a separate Cloud Run Job, so parallel cold-starting instances don't race
# on `alembic upgrade`.
if [ "${RUN_MIGRATIONS_ON_START:-true}" = "true" ]; then
  echo "[entrypoint] Running database migrations..."
  alembic upgrade head

  echo "[entrypoint] Bootstrapping admin (no-op if users already exist)..."
  python scripts/bootstrap_admin.py || echo "[entrypoint] bootstrap step skipped"
else
  echo "[entrypoint] RUN_MIGRATIONS_ON_START=false — skipping migrate/bootstrap (run the Job instead)"
fi

# Render/Cloud Run/most PaaS inject $PORT; default to 8000 locally.
PORT="${PORT:-8000}"
echo "[entrypoint] Starting uvicorn on :${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
