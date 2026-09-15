# JARVIS de Bancada

Cérebro de Engenharia Eletrônica (Streamlit): personalidade Jarvis livre + Modo Mestre Técnico — pesquisa manuais/esquemas, monta mapa de diagnóstico e aprende com seus consertos.

**Online:** https://jarvis-bancada.onrender.com/

## O que faz

1. **Personalidade livre** — conversa normal, piadas, parceiro de bancada.
2. **Modo Mestre Técnico** — ao detectar conserto, assume a liderança do diagnóstico.
3. **Pesquisa ativa** — manuais, esquemas elétricos e defeitos comuns na web.
4. **Mapa de diagnóstico** — (1) visual → (2) medições básicas → (3) componentes.
5. **Memória de aprendizado (SQLite)** — casos resolvidos em `data/brain/learning.db`; em aparelhos repetidos sugere o que já funcionou.
6. **Visão** — marca pontas do multímetro na foto + zoom.
7. **Banco de falhas (JSON)** — espelho local além do SQLite.
8. **Esquema/PDF**, checklist de segurança, TTS, PWA, HUD.

Também: escuta contínua (Web Speech), Whisper, chat aberto sem formulário.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# OPENAI_API_KEY ou ANTHROPIC_API_KEY
```

## Executar

```bash
streamlit run app.py --server.port 3847 --server.address 0.0.0.0
```

Abra http://127.0.0.1:3847

Sem API key sobe em **modo demo**.

### Temperatura real do PC (bancada)

No **Windows da oficina**:

```bash
python scripts/sensor_local.py
```

Deixe rodando e abra o JARVIS **no mesmo PC**. Em **Sistemas** aparece CPU/RAM/temp locais.

No site Render as % são do **servidor**, não do seu PC.

## Testes rápidos

```bash
.venv/bin/python scripts/test_features.py
```

## Keep-alive (anti-sleep Render Free)

Workflow: `.github/workflows/keep-alive.yml` (cron `*/5`).  
No GitHub: **Actions → Enable workflows** se estiver desativado.  
Opcional: UptimeRobot a cada 5 min no mesmo URL.

## Riscos

- Render Free pode dormir se o ping falhar (cold start 30–60s).
- GPT-5.5 consome créditos da API.
- Temperatura no cloud ≠ PC da bancada.
- Não compartilhe a chave API.
- Alta tensão: EPI e isolamento são sua responsabilidade.

## Estrutura

```
app.py
agent/           # diagnostic, llm, memory, vision, voice, docs, failures, safety, profile, system_hud
static/          # PWA
data/cases/      # histórico
scripts/sensor_local.py
scripts/test_features.py
.github/workflows/keep-alive.yml
```

## Deploy automático (Render)

O serviço **https://jarvis-bancada.onrender.com/** está ligado ao GitHub
`marketingyahoo59-sketch/-JARVIS-BANCADA` com **Auto-Deploy**.

Cada `bash scripts/push-github.sh` (ou push para `main`) atualiza o site sozinho.
Keep-alive: GitHub Action a cada 5 min (`.github/workflows/keep-alive.yml`).

Opcional: coloque `RENDER_API_KEY` no `.env` para forçar deploy via API além do auto-deploy.
