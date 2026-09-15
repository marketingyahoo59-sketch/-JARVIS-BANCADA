#!/usr/bin/env bash
# Publica JARVIS na Render (servidor próprio, grátis).
# Uso: RENDER_API_KEY=rnd_xxx OPENAI_API_KEY=sk-xxx bash deploy/render-up.sh
set -euo pipefail

: "${RENDER_API_KEY:?Defina RENDER_API_KEY}"
: "${OPENAI_API_KEY:?Defina OPENAI_API_KEY}"

OWNER_ID=$(curl -sS -H "Authorization: Bearer $RENDER_API_KEY" \
  https://api.render.com/v1/owners | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["owner"]["id"] if isinstance(d,list) else d["owner"]["id"])')

echo "Owner: $OWNER_ID"

# Cria serviço a partir do Git (precisa repo público/GitHub conectado) OU usa deploy tarball
# Aqui: sobe como serviço blueprints se já existir; senão cria web service genérico.

BODY=$(python3 - <<PY
import json, os
print(json.dumps({
  "type": "web_service",
  "name": "jarvis-bancada",
  "ownerId": os.environ["OWNER_ID"],
  "runtime": "python",
  "plan": "free",
  "region": "oregon",
  "buildCommand": "pip install -r requirements.txt",
  "startCommand": "streamlit run app.py --server.port=\$PORT --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false",
  "envVars": [
    {"key": "LLM_PROVIDER", "value": "openai"},
    {"key": "OPENAI_MODEL", "value": "gpt-5.5"},
    {"key": "OPENAI_API_KEY", "value": os.environ["OPENAI_API_KEY"]},
    {"key": "WHISPER_MODEL", "value": "whisper-1"},
    {"key": "TTS_MODEL", "value": "gpt-4o-mini-tts"},
    {"key": "TTS_VOICE", "value": "nova"},
  ],
}))
PY
)

# Nota: a API Render exige repo GitHub conectado para web_service padrão.
# Se falhar, o painel New > Blueprint com render.yaml é o caminho.
curl -sS -X POST "https://api.render.com/v1/services" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY" | tee /tmp/render-create.json

echo
echo "Se a API pedir repositório GitHub: no painel Render → New → Web Service → conecte o repo e use o render.yaml."
