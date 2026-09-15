#!/usr/bin/env bash
# Envia main → GitHub. O Render (jarvis-bancada.onrender.com) faz Auto-Deploy sozinho.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GITHUB_TOKEN:=${GH_TOKEN:-}}"
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Falta GITHUB_TOKEN no .env" >&2
  exit 1
fi

export GITHUB_TOKEN GH_TOKEN="$GITHUB_TOKEN"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SHA="$(git rev-parse --short HEAD)"

echo "==> Push GitHub ($BRANCH @ $SHA)"
git push github "$BRANCH"

RENDER_URL="${RENDER_URL:-https://jarvis-bancada.onrender.com/}"
RENDER_SERVICE_ID="${RENDER_SERVICE_ID:-srv-dakalouk1f9s73ck9q8g}"

# Se tiver RENDER_API_KEY, força um deploy (além do auto-deploy do GitHub)
if [[ -n "${RENDER_API_KEY:-}" ]]; then
  echo "==> Disparando deploy Render API ($RENDER_SERVICE_ID)"
  curl -sS -X POST \
    "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys" \
    -H "Authorization: Bearer ${RENDER_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"clearCache":"do_not_clear"}' \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print("deploy", d.get("id") or d.get("deploy",{}).get("id") or d)' \
    || echo "(API Render falhou — Auto-Deploy do GitHub ainda vale)"
fi

echo "==> GitHub OK. Render Auto-Deploy deve pegar o commit $SHA"
echo "    URL: $RENDER_URL"

# Ping leve (pode demorar no cold start)
code=$(curl -sS -m 60 -o /dev/null -w "%{http_code}" "$RENDER_URL" || echo 000)
echo "    ping HTTP $code"
echo "Pronto."
