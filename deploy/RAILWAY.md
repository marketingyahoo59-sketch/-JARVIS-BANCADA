# Deploy JARVIS no Railway (sem cold start do Free + disco permanente)

## Por quê sair do Render Free

| Problema Render Free | No Railway |
|---|---|
| Dorme (~30s cold start) | Fica acordado no plano pago mínimo |
| Disco apaga no redeploy | **Volume** gruda em `/data` |
| Pouca RAM | Dá para subir o plano se precisar |

## Passo a passo (10 min)

1. Crie conta em https://railway.app e ligue o GitHub.
2. **New Project → Deploy from GitHub repo** → escolha `-JARVIS-BANCADA`.
3. Railway detecta o `Dockerfile` automaticamente.
4. Em **Variables**, adicione:

```
OPENAI_API_KEY=sk-...
JARVIS_DATA_DIR=/data
JARVIS_TTS=edge
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
```

Para visão de placa melhor: `OPENAI_MODEL=gpt-4o`.

5. **Volume persistente (obrigatório para memória):**
   - No serviço → **Settings** ou aba **Volumes** → **Add Volume**
   - Mount path: `/data`
   - Tamanho: 1 GB basta no início

6. **Networking** → Generate Domain (HTTPS público).

7. Cada `git push` em `main` atualiza o app; o volume `/data` **não** é apagado.

## O que fica salvo em `/data`

```
/data/brain/learning.db   # aprendizado SQLite
/data/cases/              # histórico de chats/casos
/data/uploads/            # fotos
/data/failures/           # banco JSON
/data/profile.json        # perfil (Sr. Igor)
```

## Teste local com a mesma pasta

```bash
export JARVIS_DATA_DIR=./data
export JARVIS_TTS=edge
streamlit run app.py --server.port 3847
```

## Alternativas

- **VPS Hetzner/DigitalOcean (~US$5/mês):** máximo controle, zero sleep. Use o mesmo `Dockerfile` + `docker compose` com volume.
- **PC da oficina + Cloudflare Tunnel:** custo zero de hosting; bom se quiser sensores físicos.

## Migrar dados do Render (se ainda existirem)

No Render Free o disco costuma já ter sido perdido. Se tiver backup local de `data/`, copie para o volume:

```bash
railway volume  # ou use o file browser / scp na VPS
```

Ou rode o JARVIS uma vez local, marque casos resolvidos, e faça upload da pasta `data/` no volume.
