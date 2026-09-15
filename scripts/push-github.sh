#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# load .env token
export GITHUB_TOKEN="$(grep -E '^GITHUB_TOKEN=' .env | head -1 | cut -d= -f2-)"
export GH_TOKEN="$GITHUB_TOKEN"
git push github main
echo "GitHub atualizado: $(git rev-parse --short HEAD)"
