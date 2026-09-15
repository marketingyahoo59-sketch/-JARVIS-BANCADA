# JARVIS sem dormir — Fly.io

O Render **Free** dorme ~15 min sem tráfego. No **Fly.io** o free allowance costuma manter a app acordada se configurares `min_machines_running = 1` (consome crédito grátis do mês).

## 1. Conta

1. Cria conta em https://fly.io
2. Instala CLI: https://fly.io/docs/hands-on/install-flyctl/
3. `fly auth login`

## 2. Deploy (na pasta do projeto)

```bash
fly launch --name jarvis-bancada --region gru --no-deploy
fly secrets set OPENAI_API_KEY=sk-... LLM_PROVIDER=openai OPENAI_MODEL=gpt-5.5
fly deploy
```

O ficheiro `fly.toml` já está neste repo.

## 3. Manter acordado

Em `fly.toml`:

```toml
[http_service]
  min_machines_running = 1
```

Sem cartão o crédito grátis acaba; depois ou pagas pouco ou volta a dormir.
