# Postgres client tools for the Railway → Neon data copy, run as a Cloud Run Job.
# Keeping this in the cloud means no local pg_dump install and no DB credentials on a
# workstation — both URLs come from Secret Manager at run time.
#
# PG 18 client matches Neon's server version and can still dump older source servers.
FROM postgres:18-alpine

COPY copy.sh /copy.sh
# Read-only verification, run with `--command sh --args /check.sh` on the same job image.
COPY check.sh /check.sh
# Creates a database (used to provision the staging environment).
COPY mkdb.sh /mkdb.sh
# Disaster-recovery drill: dump production, restore to a throwaway db, verify, drop.
COPY drill.sh /drill.sh
RUN chmod +x /copy.sh /check.sh /mkdb.sh /drill.sh

ENTRYPOINT ["/copy.sh"]
