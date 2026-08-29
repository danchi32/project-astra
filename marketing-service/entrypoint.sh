#!/usr/bin/env bash
# Production startup. Migrations are NOT run here.
set -euo pipefail

# The product backend learned this the hard way and the same rule applies: on Cloud Run,
# several instances cold-start in parallel and would race each other on `alembic upgrade`.
# Migrations run once, from the astra-marketing-migrate Job, before the revision rolls.
# The flag exists so a single-instance local or staging run can still self-migrate.
if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] Running database migrations..."
  alembic upgrade head
else
  echo "[entrypoint] RUN_MIGRATIONS_ON_START=false — migrations are the Job's responsibility"
fi

PORT="${PORT:-8080}"
echo "[entrypoint] Starting uvicorn on :${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
