#!/usr/bin/env bash
# One-command build → push → migrate → deploy to Google Cloud Run.
#
# The parallel "warm standby": run this whenever you want to (re)deploy the standby
# Cloud Run service. It does NOT touch DNS — api.technomateai.com keeps pointing at
# Railway until you flip it (see docs/MIGRATION_CLOUDRUN_NEON.md). Test the standby on
# its *.run.app URL; flip the domain only when you're ready.
#
# Prereqs: gcloud authed; secrets already created in Secret Manager (see env.cloudrun.example);
# Artifact Registry repo `astra` exists in the region.
#
# Usage:
#   PROJECT_ID=my-proj REGION=asia-south1 ./deploy/cloudrun-deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-astra-backend}"
REPO="${REPO:-astra}"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:${TAG}"

echo "==> Building $IMAGE"
docker build -t "$IMAGE" .
docker push "$IMAGE"

# Secrets to wire in (must already exist in Secret Manager). Add/remove to match your setup.
SECRETS="DATABASE_URL=DATABASE_URL:latest"
SECRETS="${SECRETS},JWT_SECRET_KEY=JWT_SECRET_KEY:latest"
SECRETS="${SECRETS},REDIS_URL=REDIS_URL:latest"
SECRETS="${SECRETS},QDRANT_URL=QDRANT_URL:latest"
SECRETS="${SECRETS},QDRANT_API_KEY=QDRANT_API_KEY:latest"
SECRETS="${SECRETS},RESEND_API_KEY=RESEND_API_KEY:latest"
SECRETS="${SECRETS},RAZORPAY_KEY_ID=RAZORPAY_KEY_ID:latest"
SECRETS="${SECRETS},RAZORPAY_KEY_SECRET=RAZORPAY_KEY_SECRET:latest"
SECRETS="${SECRETS},RAZORPAY_WEBHOOK_SECRET=RAZORPAY_WEBHOOK_SECRET:latest"

# Non-secret env. The domain stays the same so agents/webhooks don't change.
ENVVARS="RUN_MIGRATIONS_ON_START=false"
ENVVARS="${ENVVARS},PUBLIC_API_URL=https://api.technomateai.com"
ENVVARS="${ENVVARS},PUBLIC_APP_URL=https://astra.technomateai.com"
ENVVARS="${ENVVARS},CORS_ORIGINS=https://astra.technomateai.com"
ENVVARS="${ENVVARS},AGENT_BACKEND_IP="

echo "==> Running migrations as a one-off Job (avoids multi-instance races)"
gcloud run jobs deploy astra-migrate --image "$IMAGE" --region "$REGION" \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest" \
  --command alembic --args upgrade,head --quiet
gcloud run jobs execute astra-migrate --region "$REGION" --wait

echo "==> Deploying service $SERVICE"
gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" \
  --min-instances 1 --max-instances 10 --concurrency 80 --port 8000 \
  --allow-unauthenticated \
  --set-secrets "$SECRETS" \
  --set-env-vars "$ENVVARS"

echo "==> Done. Test the standby:"
gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
echo "   curl \$(above)/health   # should be ok — this is the parallel env, DNS still on Railway"
