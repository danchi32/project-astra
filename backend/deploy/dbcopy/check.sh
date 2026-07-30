#!/bin/sh
# Read-only report on the destination database, run as a Cloud Run Job.
#
# Kept as a file rather than an inline `--args` query on purpose: gcloud splits --args on
# commas, and Git Bash rewrites POSIX-looking args into Windows paths — so a script baked
# into the image is the only reliable way to run non-trivial SQL here. Run it from
# PowerShell:  gcloud run jobs execute astra-dbcheck --region asia-southeast1 --wait
#
# Needs MIGRATE_DST_URL (from Secret Manager). SELECTs only — changes nothing.
# Deliberately reports counts, hostnames and org names but no user emails or other PII.
set -eu

: "${MIGRATE_DST_URL:?MIGRATE_DST_URL is required}"

q() { psql "$MIGRATE_DST_URL" -P pager=off -c "$1"; }

echo "==> Schema version"
psql "$MIGRATE_DST_URL" -P pager=off -tAc "select 'alembic_version = ' || version_num from alembic_version"

echo "==> Table row counts"
q "
  select 'organizations'         as table, count(*) from organizations
  union all select 'users',               count(*) from users
  union all select 'devices',             count(*) from devices
  union all select 'assets',              count(*) from assets
  union all select 'remediation_tasks',   count(*) from remediation_tasks
  union all select 'audit_logs',          count(*) from audit_logs
  union all select 'telemetry_snapshots', count(*) from telemetry_snapshots
  union all select 'telemetry_rollups',   count(*) from telemetry_daily_rollups
  union all select 'device_installed_apps', count(*) from device_installed_apps
  union all select 'device_services',     count(*) from device_services
  union all select 'device_windows_updates', count(*) from device_windows_updates
  union all select 'device_event_logs',   count(*) from device_event_logs
  order by 1;
"

echo "==> Organizations (what the portal should list)"
q "
  select o.name,
         (select count(*) from users   u where u.org_id = o.id) as users,
         (select count(*) from devices d where d.org_id = o.id) as devices,
         (select count(*) from assets  a where a.org_id = o.id) as assets
  from organizations o
  order by devices desc, o.name;
"

echo "==> Devices (hostname / OS / agent / last seen)"
q "
  select d.hostname,
         left(d.os_version, 22)  as os,
         d.agent_version         as agent,
         to_char(d.last_seen_at, 'YYYY-MM-DD HH24:MI') as last_seen,
         case when d.last_seen_at > now() - interval '5 minutes'
              then 'online' else 'offline' end as status
  from devices d
  order by d.last_seen_at desc nulls last;
"

echo "==> Data the Compliance + Fleet pages read"
q "
  select 'pending windows updates' as signal, count(*) from device_windows_updates where is_installed = false
  union all select 'critical events',    count(*) from device_event_logs where level = 'Critical'
  union all select 'error events',       count(*) from device_event_logs where level = 'Error'
  union all select 'banned software rules', count(*) from banned_software
  union all select 'devices with telemetry', count(distinct device_id) from telemetry_snapshots
  order by 1;
"

echo "==> Rollup backfill (migration 0035) — did history survive pruning?"
q "
  select count(*)                  as rollup_rows,
         count(distinct device_id) as devices_covered,
         min(day)                  as earliest_day,
         max(day)                  as latest_day,
         sum(samples)              as snapshots_aggregated
  from telemetry_daily_rollups;
"

echo "==> Done."
