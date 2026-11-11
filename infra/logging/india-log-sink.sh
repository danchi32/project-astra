#!/usr/bin/env bash
# Z1 — keep SAVIO's production logs in India for at least a year.
#
# Why: CERT-In (Apr 2022 directions) wants ICT system logs kept 180 days *within India*;
# the DPDP Rules want processing logs kept at least a year. Out of the box this project
# writes everything to the `_Default` bucket, which lives in `global` and keeps 30 days —
# neither in India nor long enough. (`_Required`, 400 days, holds only Google's own
# admin-activity audit logs, not ours.)
#
# What: a log bucket in asia-south1 (Mumbai) with RETENTION_DAYS, and a sink that copies
# every log entry in the project into it. `_Default` is left exactly as it is, so the
# console's Logs Explorer and every existing `gcloud logging read` keep working; the India
# bucket is the copy we are allowed to rely on.
#
# Idempotent: run it again after changing a value below and it updates in place. That is
# the point of a script — retention set by hand in the console is invisible to review and
# is gone the day someone recreates the bucket.
#
# Usage (needs roles/logging.configWriter on the project):
#   infra/logging/india-log-sink.sh --dry-run   # print the commands, change nothing
#   infra/logging/india-log-sink.sh             # apply
#   infra/logging/india-log-sink.sh --verify    # show settings + the newest entry that landed
#
# ponytail: the bucket is not locked. Locking makes the retention impossible to shorten
# (or the bucket to delete) — ever — so it waits for the lawyer's answer on retention (Z6).
# Upgrade path: `gcloud logging buckets update india-logs --location asia-south1 --locked`.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-astra-prod-503923}"
LOCATION="asia-south1"
BUCKET="india-logs"
SINK="india-logs"
RETENTION_DAYS=400
# Matches every entry (every entry has a severity, DEFAULT being the lowest). Written out
# rather than left empty so a filter someone adds by hand is reset by the next run.
FILTER='severity>=DEFAULT'

DEST="logging.googleapis.com/projects/${PROJECT_ID}/locations/${LOCATION}/buckets/${BUCKET}"
MODE="${1:-apply}"

run() {
  echo "+ $*"
  if [ "$MODE" != "--dry-run" ]; then "$@"; fi
}

if [ "$MODE" = "--verify" ]; then
  gcloud logging buckets describe "$BUCKET" --location "$LOCATION" --project "$PROJECT_ID" \
    --format="table(name.basename(),retentionDays,locked,lifecycleState)"
  gcloud logging sinks describe "$SINK" --project "$PROJECT_ID" --format="table(name,destination,filter)"
  echo "Newest entry in the India bucket:"
  gcloud logging read "$FILTER" --project "$PROJECT_ID" --bucket "$BUCKET" --location "$LOCATION" \
    --view _AllLogs --limit 1 --freshness 1d \
    --format="table(timestamp,resource.type,logName.basename())"
  exit 0
fi

if gcloud logging buckets describe "$BUCKET" --location "$LOCATION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  run gcloud logging buckets update "$BUCKET" --location "$LOCATION" --project "$PROJECT_ID" \
    --retention-days "$RETENTION_DAYS"
else
  run gcloud logging buckets create "$BUCKET" --location "$LOCATION" --project "$PROJECT_ID" \
    --retention-days "$RETENTION_DAYS" \
    --description "All SAVIO production logs, kept in India (CERT-In 180 d, DPDP 1 y). Managed by infra/logging/india-log-sink.sh"
fi

# A sink into a log bucket in the same project needs no IAM grant for its writer identity.
if gcloud logging sinks describe "$SINK" --project "$PROJECT_ID" >/dev/null 2>&1; then
  run gcloud logging sinks update "$SINK" "$DEST" --project "$PROJECT_ID" --log-filter "$FILTER"
else
  run gcloud logging sinks create "$SINK" "$DEST" --project "$PROJECT_ID" --log-filter "$FILTER" \
    --description "Copies every log entry to the India bucket. Managed by infra/logging/india-log-sink.sh"
fi

echo "Done. New entries reach the bucket within a minute or two; check with: $0 --verify"
