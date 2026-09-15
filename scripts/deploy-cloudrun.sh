#!/usr/bin/env bash
# Deploy JARVIS → Google Cloud Run + bucket GCS
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-jarvis-bancada}"
BUCKET="${BUCKET:-${PROJECT_ID}-jarvis-data}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}:latest"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Defina PROJECT_ID ou rode: gcloud config set project SEU_ID"
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  # tenta .env
  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    set -a; source .env; set +a
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Exporte OPENAI_API_KEY=sk-... antes do deploy"
  exit 1
fi

echo "==> Projeto: $PROJECT_ID | Região: $REGION | Serviço: $SERVICE"
echo "==> Bucket: gs://$BUCKET"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com --project "$PROJECT_ID"

if ! gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
  echo "==> Criando bucket gs://${BUCKET}"
  gsutil mb -l "$REGION" -p "$PROJECT_ID" "gs://${BUCKET}"
fi

echo "==> Build & push imagem"
gcloud builds submit --tag "$IMAGE" --project "$PROJECT_ID"

echo "==> Deploy Cloud Run"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars "GCS_BUCKET=${BUCKET},GCS_PREFIX=jarvis,JARVIS_DATA_DIR=/tmp/jarvis-data,JARVIS_TTS=edge,OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o-mini},LLM_PROVIDER=openai" \
  --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest" \
  --project "$PROJECT_ID" \
  || gcloud run deploy "$SERVICE" \
    --image "$IMAGE" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY},GCS_BUCKET=${BUCKET},GCS_PREFIX=jarvis,JARVIS_DATA_DIR=/tmp/jarvis-data,JARVIS_TTS=edge,OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o-mini},LLM_PROVIDER=openai" \
    --project "$PROJECT_ID"

# IAM bucket para a service account padrão do Compute
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "==> IAM objectAdmin para ${SA}"
gsutil iam ch "serviceAccount:${SA}:roles/storage.objectAdmin" "gs://${BUCKET}" || true

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
echo ""
echo "Pronto: $URL"
echo "Memória: gs://${BUCKET}/jarvis/"
echo "Guia: deploy/CLOUDRUN.md"
