# JARVIS de Bancada

Cérebro de Engenharia Eletrônica (Streamlit): Jarvis livre + Modo Mestre Técnico.

**Hospedagem: só Google Cloud Run + Cloud Storage.**  
Guia: **[deploy/CLOUDRUN.md](deploy/CLOUDRUN.md)**

## O que faz

1. **Personalidade livre** — conversa, piadas, parceiro de bancada (tom JARVIS, sem robô).
2. **Modo Mestre Técnico** — lidera o conserto quando detecta diagnóstico.
3. **Pesquisa ativa** — manuais/esquemas/defeitos; só com **modelo concreto** (filtra lixo web).
4. **Mapa de diagnóstico** — visual → medições → componentes.
5. **Hotwords** — `anota: …` e `próxima etapa`.
6. **Memória** — SQLite + fotos no **bucket GCS** (`GCS_BUCKET`).
7. **Visão**, falhas, PDF, segurança, TTS (edge), PWA, HUD.
8. **Voz estável** — mic via `st.audio_input` (iframe contínuo removido: corrigia o crash `removeChild`).
9. **Operador autônomo** — loop ANALISAR → PLANEJAR → EXECUTAR → VERIFICAR. Tools de cena: `set_layout`, `close_all_modules`, `focus_component`. Proativo em tensão/temp/erro de HUD.
10. **Self-heal + Event Bus** — captura erros JS e remonta módulos; toasts/SFX/telemetria live sem reload manual.

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# OPENAI_API_KEY=...
streamlit run app.py --server.port 3847 --server.address 0.0.0.0
```

## Deploy Google

```bash
export OPENAI_API_KEY=sk-...
bash scripts/deploy-cloudrun.sh
```

Ou Continuous Deploy pelo console (GitHub → Cloud Run), como você já está fazendo.

Variáveis principais:

| Nome | Valor |
|---|---|
| `OPENAI_API_KEY` | sua chave |
| `GCS_BUCKET` | bucket da memória |
| `JARVIS_DATA_DIR` | `/tmp/jarvis-data` |
| `JARVIS_TTS` | `edge` |
| `OPENAI_MODEL` | `gpt-4o-mini` |

## Estrutura

```
app.py
agent/               # diagnostic, llm, memory, gcs_sync…
deploy/CLOUDRUN.md
scripts/deploy-cloudrun.sh
Dockerfile
```
