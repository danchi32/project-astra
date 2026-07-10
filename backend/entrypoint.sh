#!/usr/bin/env bash
# Production startup: apply migrations, optionally seed the first admin, then serve.
set -euo pipefail

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Bootstrapping admin (no-op if users already exist)..."
python scripts/bootstrap_admin.py || echo "[entrypoint] bootstrap step skipped"

# Render/most PaaS inject $PORT; default to 8000 locally.
PORT="${PORT:-8000}"
echo "[entrypoint] Starting uvicorn on :${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
