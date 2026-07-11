#!/usr/bin/env bash
# Production startup: apply migrations, optionally seed the first admin, then serve.
set -euo pipefail

# Only run migrations if DATABASE_URL or ASTRA_DATABASE_URL is set
if [ -z "${ASTRA_DATABASE_URL:-}" ] && [ -z "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] WARNING: No database URL configured, skipping migrations"
else
    echo "[entrypoint] Running database migrations..."
    alembic upgrade head || echo "[entrypoint] Migration failed, continuing startup..."
fi

echo "[entrypoint] Bootstrapping admin (no-op if users already exist)..."
python scripts/bootstrap_admin.py || echo "[entrypoint] bootstrap step skipped"

# Render/most PaaS inject $PORT; default to 8000 locally.
PORT="${PORT:-8000}"
echo "[entrypoint] Starting uvicorn on :${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
