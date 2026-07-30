#!/bin/sh
# Read-only sanity check of the destination database, run as a Cloud Run Job.
#
# Kept as a file rather than an inline `--args` query on purpose: gcloud splits --args on
# commas and the Windows shell mangles nested quotes, so a script in the image is the only
# reliable way to run non-trivial SQL here.
#
# Needs MIGRATE_DST_URL (from Secret Manager). Touches nothing — SELECTs only.
set -eu

: "${MIGRATE_DST_URL:?MIGRATE_DST_URL is required}"

echo "==> Schema version"
psql "$MIGRATE_DST_URL" -P pager=off -tAc "select 'alembic_version = ' || version_num from alembic_version"

echo "==> Row counts"
psql "$MIGRATE_DST_URL" -P pager=off -c "
  select 'organizations'        as table, count(*) from organizations
  union all select 'users',              count(*) from users
  union all select 'devices',            count(*) from devices
  union all select 'assets',             count(*) from assets
  union all select 'remediation_tasks',  count(*) from remediation_tasks
  union all select 'audit_logs',         count(*) from audit_logs
  union all select 'telemetry_snapshots',count(*) from telemetry_snapshots
  union all select 'telemetry_rollups',  count(*) from telemetry_daily_rollups
  order by 1;
"

echo "==> Rollup backfill (migration 0035) — did history survive?"
psql "$MIGRATE_DST_URL" -P pager=off -c "
  select count(*)                        as rollup_rows,
         count(distinct device_id)       as devices_covered,
         min(day)                        as earliest_day,
         max(day)                        as latest_day,
         sum(samples)                    as snapshots_aggregated
  from telemetry_daily_rollups;
"

echo "==> Done."
