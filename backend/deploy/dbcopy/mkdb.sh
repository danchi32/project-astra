#!/bin/sh
# Create a database on the Neon project, for a staging environment.
#
# A separate DATABASE rather than a Neon branch on purpose: a branch is a copy-on-write clone
# of production, which would put real customer data in staging. Staging should be reachable by
# more people and deployed to more often, so it must not hold production data. An empty
# database that migrations run against is both safer and simpler, and it shares the existing
# Neon compute, so it costs storage only.
#
# Kept as a file because gcloud splits --args on commas and mangles quoted SQL containing
# spaces. Needs MIGRATE_DST_URL (an admin connection) and NEW_DB_NAME.
set -eu

: "${MIGRATE_DST_URL:?MIGRATE_DST_URL is required}"
: "${NEW_DB_NAME:?NEW_DB_NAME is required}"

# CREATE DATABASE cannot run inside a transaction; psql -c is autocommit, so this is fine.
if psql "$MIGRATE_DST_URL" -tAc "select 1 from pg_database where datname = '$NEW_DB_NAME'" | grep -q 1; then
  echo "database '$NEW_DB_NAME' already exists — nothing to do"
else
  echo "creating database '$NEW_DB_NAME'"
  psql "$MIGRATE_DST_URL" -c "CREATE DATABASE $NEW_DB_NAME"
  echo "created"
fi

echo "==> databases on this project"
psql "$MIGRATE_DST_URL" -P pager=off -c "select datname from pg_database where datistemplate = false order by 1"
