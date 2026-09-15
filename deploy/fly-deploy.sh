#!/usr/bin/env bash
# Deploy JARVIS no Fly.io (não dorme).
# Uso:
#   export FLY_API_TOKEN='FlyV1 ...'
#   export OPENAI_API_KEY='sk-...'   # ou já está no .env
#   bash deploy/fly-deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.fly/bin:${PATH}"

: "${FLY_API_TOKEN:?Cole o token Fly.io (https://fly.io/user/personal_access_tokens)}"

if [[ -z "${OPENAI_API_KEY:-}" && -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi
: "${OPENAI_API_KEY:?Defina OPENAI_API_KEY}"

APP="${FLY_APP_NAME:-jarvis-bancada}"
ORG="${FLY_ORG:-personal}"

echo "==> App: $APP (região gru)"
fly apps create "$APP" --org "$ORG" 2>/dev/null || echo "(app já existe)"

echo "==> Secrets"
fly secrets set \
  OPENAI_API_KEY="$OPENAI_API_KEY" \
  LLM_PROVIDER=openai \
  OPENAI_MODEL="${OPENAI_MODEL:-gpt-5.5}" \
  -a "$APP"

echo "==> Deploy"
fly deploy -a "$APP" --ha=false

echo ""
echo "Pronto: https://${APP}.fly.dev"
fly status -a "$APP" || true
