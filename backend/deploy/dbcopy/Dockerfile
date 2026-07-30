# Postgres client tools for the Railway → Neon data copy, run as a Cloud Run Job.
# Keeping this in the cloud means no local pg_dump install and no DB credentials on a
# workstation — both URLs come from Secret Manager at run time.
#
# PG 18 client matches Neon's server version and can still dump older source servers.
FROM postgres:18-alpine

COPY copy.sh /copy.sh
# Read-only verification, run with `--command /check.sh` on the same job image.
COPY check.sh /check.sh
RUN chmod +x /copy.sh /check.sh

ENTRYPOINT ["/copy.sh"]
