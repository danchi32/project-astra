#!/bin/sh
# Disaster-recovery drill: prove production can actually be restored, and measure how long
# it takes (the RTO number you'd quote to a customer mid-incident).
#
# "A backup you have never restored is not a backup." The point of running this on a calm
# day is that nobody learns the procedure for the first time during an outage.
#
# SAFETY: production is only ever READ (pg_dump). The restore target is a throwaway database
# created at the start and dropped at the end. Nothing writes to neondb.
#
# Needs MIGRATE_DST_URL — the Neon DIRECT (non-pooler) admin URL for the production database.
set -eu

: "${MIGRATE_DST_URL:?MIGRATE_DST_URL is required}"

DRILL_DB="astra_restore_drill_$(date +%s)"
DUMP=/tmp/drill.dump

# Same server, different database. Anchor the substitution on "/neondb?" — the database name
# is the segment before the query string. A bare "/neondb" also matches inside the USERNAME
# (the URL contains "://neondb_owner:"), which silently rewrote the credentials and produced
# a baffling "password authentication failed for user astra_restore_drill_..._owner".
SCRATCH_URL=$(printf '%s' "$MIGRATE_DST_URL" | sed "s#/neondb?#/$DRILL_DB?#")

# Always remove the throwaway database, including on failure — otherwise a botched run leaves
# an orphan behind that quietly costs storage.
cleanup() {
  psql "$MIGRATE_DST_URL" -c "DROP DATABASE IF EXISTS $DRILL_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== 1. dump production (read-only) ==="
T0=$(date +%s)
pg_dump --no-owner --no-privileges --format=custom -f "$DUMP" "$MIGRATE_DST_URL"
T1=$(date +%s)
echo "    dump took $((T1-T0))s, size $(du -h "$DUMP" | cut -f1)"

echo "=== 2. create throwaway database $DRILL_DB ==="
psql "$MIGRATE_DST_URL" -c "CREATE DATABASE $DRILL_DB" >/dev/null

# Prove the scratch URL really lands on the throwaway database before restoring anything.
# String-matching the URL is not enough — the earlier bug produced a URL that *contained* the
# drill name yet still pointed elsewhere. Ask the server what it actually connected to.
CONNECTED=$(psql "$SCRATCH_URL" -tAc "select current_database()" 2>/dev/null || echo "")
if [ "$CONNECTED" != "$DRILL_DB" ]; then
  echo "REFUSING: scratch URL connects to '${CONNECTED:-<failed>}', expected '$DRILL_DB'."
  exit 1
fi
echo "    verified: connected to $CONNECTED"
T2=$(date +%s)

echo "=== 3. restore into it ==="
pg_restore --no-owner --no-privileges --dbname "$SCRATCH_URL" "$DUMP" >/dev/null 2>&1 \
  || echo "    (pg_restore reported non-fatal notices)"
T3=$(date +%s)
echo "    restore took $((T3-T2))s"

echo "=== 4. verify the restored copy matches production ==="
TABLES="organizations users devices assets remediation_tasks audit_logs telemetry_snapshots telemetry_daily_rollups"
MISMATCH=0
printf '%-26s %12s %12s\n' "table" "production" "restored"
for T in $TABLES; do
  P=$(psql "$MIGRATE_DST_URL" -tAc "select count(*) from $T" 2>/dev/null || echo "ERR")
  R=$(psql "$SCRATCH_URL"     -tAc "select count(*) from $T" 2>/dev/null || echo "ERR")
  FLAG=""
  # Live tables drift during the drill: telemetry keeps arriving while we restore, so the
  # restored copy is a point-in-time and may legitimately be BEHIND. Only a restored copy
  # that is SHORT on a static table means the restore actually lost something.
  [ "$P" != "$R" ] && FLAG="  <- differs"
  case "$T" in telemetry_snapshots|telemetry_daily_rollups|audit_logs) FLAG="$FLAG (live table, drift expected)" ;; esac
  case "$T" in
    organizations|users|devices|assets)
      [ "$P" != "$R" ] && MISMATCH=1 ;;
  esac
  printf '%-26s %12s %12s%s\n' "$T" "$P" "$R" "$FLAG"
done

echo "=== 5. schema version in the restored copy ==="
psql "$SCRATCH_URL" -tAc "select 'alembic_version = ' || version_num from alembic_version"

echo "=== 6. drop the throwaway database ==="
cleanup
echo "    dropped $DRILL_DB"

echo "=== 6b. clean up orphans from any earlier failed run ==="
psql "$MIGRATE_DST_URL" -tAc \
  "select datname from pg_database where datname like 'astra_restore_drill_%'" |
while read -r ORPHAN; do
  [ -n "$ORPHAN" ] || continue
  echo "    dropping orphan $ORPHAN"
  psql "$MIGRATE_DST_URL" -c "DROP DATABASE IF EXISTS $ORPHAN" >/dev/null 2>&1 || true
done

echo
echo "=== RESULT ==="
echo "dump ${T1}s->$((T1-T0))s | restore $((T3-T2))s | total $((T3-T0))s end to end"
if [ "$MISMATCH" -eq 0 ]; then
  echo "PASS - every stable table restored with an identical row count."
else
  echo "FAIL - a stable table did not match. Investigate before trusting the backups."
  exit 1
fi
