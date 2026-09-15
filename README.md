# JARVIS de Bancada

Cérebro de Engenharia Eletrônica (Streamlit): Jarvis livre + Modo Mestre Técnico — pesquisa, mapa de diagnóstico e aprendizado com seus consertos.

**Online (Render Free — pode dormir):** https://jarvis-bancada.onrender.com/

**Recomendado para bancada real:** [Railway com Volume](deploy/RAILWAY.md) — resposta rápida + SQLite/fotos permanentes.

## O que faz

1. **Personalidade livre** — conversa, piadas, parceiro de bancada.
2. **Modo Mestre Técnico** — lidera o conserto quando detecta diagnóstico.
3. **Pesquisa ativa** — manuais/esquemas/defeitos (só quando precisa; timeout 6s).
4. **Mapa de diagnóstico** — visual → medições → componentes.
5. **Memória SQLite** — `data/brain/learning.db` (Railway: volume `/data`).
6. **Visão**, falhas JSON, PDF, segurança, TTS rápido (edge), PWA, HUD.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# OPENAI_API_KEY=...
# JARVIS_TTS=edge
```

## Executar

```bash
streamlit run app.py --server.port 3847 --server.address 0.0.0.0
```

http://127.0.0.1:3847

## Deploy rápido (Railway)

Guia: **[deploy/RAILWAY.md](deploy/RAILWAY.md)**

1. Deploy do GitHub no Railway (Dockerfile).
2. Vars: `OPENAI_API_KEY`, `JARVIS_DATA_DIR=/data`, `JARVIS_TTS=edge`, `OPENAI_MODEL=gpt-4o-mini`.
3. **Volume** em `/data` (obrigatório para não perder aprendizado).
4. Push em `main` atualiza; o volume permanece.

## Por que o Render Free trava

- Cold start ~30s (dorme).
- Disco efêmero (perde DB/fotos).
- Pouca RAM para voz/visão.

## Estrutura

```
app.py
agent/            # diagnostic, llm, memory, learning_db, paths…
data/             # local; produção = volume /data
deploy/RAILWAY.md
Dockerfile
railway.toml
```
