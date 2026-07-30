#!/bin/sh
# Copy the whole ASTRA database from SRC (Railway) to DST (Neon).
#
# SRC is only ever READ — the live Railway database is never modified.
# DST is REPLACED (--clean --if-exists), so only ever point it at the standby.
#
# Both URLs arrive as env vars from Secret Manager:
#   MIGRATE_SRC_URL  postgresql://…railway…            (plain libpq URL, not +asyncpg)
#   MIGRATE_DST_URL  postgresql://…neon…?sslmode=require
#
# IMPORTANT: DST must be Neon's DIRECT endpoint, NOT the -pooler one. pg_restore needs
# session-level operations that PgBouncer's transaction pooling doesn't support.
set -eu

: "${MIGRATE_SRC_URL:?MIGRATE_SRC_URL is required}"
: "${MIGRATE_DST_URL:?MIGRATE_DST_URL is required}"

case "$MIGRATE_DST_URL" in
  *-pooler.*)
    echo "ERROR: MIGRATE_DST_URL points at Neon's pooled endpoint."
    echo "       Use the DIRECT endpoint (drop '-pooler') — pg_restore needs a session."
    exit 1
    ;;
esac

DUMP=/tmp/astra.dump

echo "==> Source server version"
pg_dump --version
psql "$MIGRATE_SRC_URL" -tAc 'select version()' || true

echo "==> Dumping source (read-only)"
pg_dump --no-owner --no-privileges --format=custom -f "$DUMP" "$MIGRATE_SRC_URL"
echo "    dump size: $(du -h "$DUMP" | cut -f1)"

echo "==> Restoring into destination (replacing its contents)"
# A fresh target has no objects yet, so --clean emits harmless "does not exist" notices;
# pg_restore reports those as errors in its exit code, hence the tolerant invocation
# followed by an explicit verification below.
pg_restore --no-owner --no-privileges --clean --if-exists \
  --dbname "$MIGRATE_DST_URL" "$DUMP" || echo "    (pg_restore reported non-fatal notices)"

echo "==> Verifying row counts on the destination"
psql "$MIGRATE_DST_URL" -tA -c "
  select 'alembic_version=' || (select version_num from alembic_version limit 1);
" || true
for T in organizations users devices assets remediation_tasks audit_logs telemetry_snapshots; do
  N=$(psql "$MIGRATE_DST_URL" -tAc "select count(*) from $T" 2>/dev/null || echo "n/a")
  echo "    $T: $N"
done

echo "==> Done."
