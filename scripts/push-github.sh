#!/usr/bin/env bash
# Envia main → GitHub (fonte do deploy no Cloud Run).
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

echo "==> GitHub OK. Se o Cloud Run estiver com Continuous Deploy, ele puxa sozinho."
echo "    Guia: deploy/CLOUDRUN.md"
echo "    Deploy manual: bash scripts/deploy-cloudrun.sh"
echo "Pronto."
