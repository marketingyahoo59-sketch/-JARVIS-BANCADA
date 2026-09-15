# Fly.io — JARVIS sem dormir

## No site (1×)

1. Conta: https://fly.io/app/sign-up  
2. Cartão pode ser pedido (há crédito grátis).  
3. Token: https://fly.io/user/personal_access_tokens → **Create token**  
4. Cola o token no chat Cursor (`FlyV1 ...` ou `fo1_...`)

## Deploy (eu faço com o teu token)

Com `FLY_API_TOKEN` + `OPENAI_API_KEY`:

```bash
export FLY_API_TOKEN='...'
export PATH="$HOME/.fly/bin:$PATH"
fly apps create jarvis-bancada --org personal 2>/dev/null || true
fly secrets set OPENAI_API_KEY="$OPENAI_API_KEY" LLM_PROVIDER=openai -a jarvis-bancada
fly deploy -a jarvis-bancada
```

URL final: **https://jarvis-bancada.fly.dev**

## Ou no teu PC (PowerShell)

```powershell
# instala: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
cd pasta-do-jarvis
fly launch --copy-config --name jarvis-bancada --region gru --yes
fly secrets set OPENAI_API_KEY=sk-...
fly deploy
```

`min_machines_running = 1` + `auto_stop_machines = "off"` → **não dorme** (gasta o crédito free do mês).
