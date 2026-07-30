#!/usr/bin/env bash
# One-command build → migrate → deploy the ASTRA backend to Google Cloud Run.
#
# The parallel "warm standby": run this whenever you want to (re)deploy the standby
# Cloud Run service. It does NOT touch DNS — api.astra.technomateai.com keeps pointing at
# Railway until you flip it (see docs/MIGRATION_CLOUDRUN_NEON.md). Test the standby on
# its *.run.app URL; flip the domain only when you're ready.
#
# Region note: Cloud Run sits in asia-southeast1 (Singapore) to be CO-LOCATED with the
# Neon database. Cross-region compute→DB would add ~40ms to every query, and each API
# request makes several.
#
# Prereqs (one-time, already done for astra-prod-503923):
#   - APIs enabled: run, artifactregistry, secretmanager, cloudbuild
#   - Secrets in Secret Manager  → deploy/migrate-secrets.py
#   - Artifact Registry repo `astra` in the region
#   - Runtime service account granted roles/secretmanager.secretAccessor on each secret
#
# Usage (from backend/):
#   ./deploy/cloudrun-deploy.sh
#   GCLOUD='C:\path\to\gcloud.cmd' ./deploy/cloudrun-deploy.sh   # if not on PATH
set -euo pipefail

GCLOUD="${GCLOUD:-gcloud}"
REGION="${REGION:-asia-southeast1}"
SERVICE="${SERVICE:-astra-backend}"
REPO="${REPO:-astra}"
PROJECT_ID="${PROJECT_ID:-$("$GCLOUD" config get-value project 2>/dev/null | tr -d '\r')}"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:${TAG}"

echo "==> Project $PROJECT_ID / region $REGION"

# Build in the cloud (no local Docker daemon needed) and push to Artifact Registry.
echo "==> Building $IMAGE via Cloud Build"
"$GCLOUD" builds submit --tag "$IMAGE" --region "$REGION" .

# Every setting is read with the ASTRA_ prefix (config.py: env_prefix="ASTRA_").
# Secret values live in Secret Manager; only their NAMES appear here.
SECRETS="ASTRA_DATABASE_URL=ASTRA_DATABASE_URL:latest"
SECRETS="${SECRETS},ASTRA_JWT_SECRET_KEY=ASTRA_JWT_SECRET_KEY:latest"
SECRETS="${SECRETS},ASTRA_ANTHROPIC_API_KEY=ASTRA_ANTHROPIC_API_KEY:latest"
SECRETS="${SECRETS},ASTRA_RESEND_API_KEY=ASTRA_RESEND_API_KEY:latest"
SECRETS="${SECRETS},ASTRA_EMAIL_FROM=ASTRA_EMAIL_FROM:latest"
SECRETS="${SECRETS},ASTRA_PAYPAL_CLIENT_ID=ASTRA_PAYPAL_CLIENT_ID:latest"
SECRETS="${SECRETS},ASTRA_PAYPAL_CLIENT_SECRET=ASTRA_PAYPAL_CLIENT_SECRET:latest"
SECRETS="${SECRETS},ASTRA_PAYPAL_PLAN_ID=ASTRA_PAYPAL_PLAN_ID:latest"
SECRETS="${SECRETS},ASTRA_PAYPAL_WEBHOOK_ID=ASTRA_PAYPAL_WEBHOOK_ID:latest"

# Non-secret config. Same public URLs as Railway → installed agents need no change.
ENVVARS="RUN_MIGRATIONS_ON_START=false"
ENVVARS="${ENVVARS},ASTRA_ENVIRONMENT=production"
ENVVARS="${ENVVARS},ASTRA_PUBLIC_API_URL=https://api.astra.technomateai.com"
ENVVARS="${ENVVARS},ASTRA_PUBLIC_APP_URL=https://astra.technomateai.com/login"
ENVVARS="${ENVVARS},ASTRA_PRICE_PER_SEAT_CENTS=749"
ENVVARS="${ENVVARS},ASTRA_PAYPAL_SANDBOX=false"
ENVVARS="${ENVVARS},ASTRA_AGENT_UPDATE_MANIFEST_URL=https://github.com/danchi32/project-astra/releases/latest/download/manifest.json"
ENVVARS="${ENVVARS},ASTRA_AGENT_UPDATE_SIGNATURE_URL=https://github.com/danchi32/project-astra/releases/latest/download/manifest.json.sig"
ENVVARS="${ENVVARS},ASTRA_AGENT_BACKEND_IP="

# Migrations run ONCE here, not per instance — parallel cold starts would race on alembic.
# alembic/env.py calls get_settings(), which validates the whole Settings model — so the
# job needs every REQUIRED setting (database_url AND jwt_secret_key), not just the URL.
echo "==> Running migrations as a one-off Job"
"$GCLOUD" run jobs deploy astra-migrate --image "$IMAGE" --region "$REGION" \
  --set-secrets "ASTRA_DATABASE_URL=ASTRA_DATABASE_URL:latest,ASTRA_JWT_SECRET_KEY=ASTRA_JWT_SECRET_KEY:latest" \
  --command alembic --args upgrade,head --quiet
"$GCLOUD" run jobs execute astra-migrate --region "$REGION" --wait

echo "==> Deploying service $SERVICE"
"$GCLOUD" run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" \
  --min-instances 1 --max-instances 10 --concurrency 80 --port 8000 \
  --cpu 1 --memory 512Mi --timeout 60s \
  --allow-unauthenticated \
  --set-secrets "$SECRETS" \
  --set-env-vars "$ENVVARS" \
  --quiet

URL="$("$GCLOUD" run services describe "$SERVICE" --region "$REGION" --format='value(status.url)' | tr -d '\r')"
echo "==> Deployed. Standby URL: $URL"
echo "    Smoke-test:  curl $URL/health"
echo "    DNS is still on Railway — nothing switched over."
