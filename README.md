# JARVIS de Bancada

Assistente ativo de diagnóstico eletrônico (Streamlit): escuta, vê a placa, pesquisa e fala — estilo Homem de Ferro para bancada.

**Online:** https://jarvis-bancada.onrender.com/

## O que faz

1. **Visão** — marca cruzes nas pontas do multímetro na foto e mostra zoom da área.
2. **Status de voz** — chip Ouvindo / Processando / Falando.
3. **Banco de falhas** — ao marcar resolvido, salva placa/sintoma/peça para casos parecidos.
4. **Esquema/PDF** — anexa datasheet ou esquema; o texto entra no contexto do agente.
5. **Checklist de segurança** — avisos de tomada, capacitores, ESD, escala do multímetro.
6. **Fallback de voz** — TTS OpenAI; se falhar, usa edge-tts (pt-BR).
7. **PWA** — `static/manifest.json` + service worker para instalar no celular.
8. **Confirmação** — medição “errada” pede **confirmo** antes do Modo Solução.
9. **HUD / Config** — menu top estilo JARVIS, perfil do técnico (Sr. Igor), telemetria CPU/RAM/temp.
10. **Keep-alive** — GitHub Action pinga o Render a cada 5 min para reduzir sleep.

Também: escuta contínua (Web Speech), Whisper para áudio manual, pesquisa web, memória em `data/cases/`.

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
