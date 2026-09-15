#!/usr/bin/env bash
# Lê GITHUB_TOKEN do .env e autentica pushes para github.com (nunca versionar o token).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  # only export token lines safely
  TOKEN=$(grep -E '^GITHUB_TOKEN=' "$ROOT/.env" | head -1 | cut -d= -f2-)
  set +a
fi
TOKEN="${GITHUB_TOKEN:-${TOKEN:-}}"
if [[ "$1" == "get" ]]; then
  echo "username=x-access-token"
  echo "password=${TOKEN}"
fi
