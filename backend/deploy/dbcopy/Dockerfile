# Postgres client tools for the Railway → Neon data copy, run as a Cloud Run Job.
# Keeping this in the cloud means no local pg_dump install and no DB credentials on a
# workstation — both URLs come from Secret Manager at run time.
#
# PG 18 client matches Neon's server version and can still dump older source servers.
FROM postgres:18-alpine

COPY copy.sh /copy.sh
RUN chmod +x /copy.sh

ENTRYPOINT ["/copy.sh"]
