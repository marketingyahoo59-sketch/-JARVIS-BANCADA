# Deploy JARVIS no Google Cloud Run (cota grátis + bucket persistente)

## O que você ganha

- **Cloud Run**: paga só o uso; tem cota Always Free todo mês
- Conta nova: **US$ 300** de crédito (~90 dias)
- **Cloud Storage (bucket)**: fotos + SQLite + casos **não somem** no restart

## Pré-requisitos

1. Conta Google Cloud com faturamento ativado (pode ficar R$ 0 na cota)
2. `gcloud` CLI instalado: https://cloud.google.com/sdk/docs/install
3. Projeto criado no console

```bash
gcloud auth login
gcloud config set project SEU_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com
```

## 1) Criar o bucket (memória permanente)

```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1
export BUCKET="${PROJECT_ID}-jarvis-data"

gsutil mb -l $REGION gs://$BUCKET
# (opcional) versionamento
gsutil versioning set on gs://$BUCKET
```

## 2) Deploy com um comando

```bash
export OPENAI_API_KEY=sk-...
bash scripts/deploy-cloudrun.sh
```

O script:
- builda a imagem
- sobe no Cloud Run
- define `GCS_BUCKET`, `JARVIS_DATA_DIR=/tmp/jarvis-data`, `JARVIS_TTS=edge`

## 3) Variáveis importantes

| Variável | Valor |
|---|---|
| `OPENAI_API_KEY` | sua chave |
| `GCS_BUCKET` | nome do bucket |
| `GCS_PREFIX` | `jarvis` (padrão) |
| `JARVIS_DATA_DIR` | `/tmp/jarvis-data` |
| `JARVIS_TTS` | `edge` |
| `OPENAI_MODEL` | `gpt-4o-mini` (rápido) |

## 4) Permissão do Cloud Run no bucket

O script tenta conceder. Se falhar:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gsutil iam ch serviceAccount:${SA}:objectAdmin gs://$BUCKET
```

## Limitações (seja honesto)

- **Cold start**: se ninguém usar, o Cloud Run “dorme” (~alguns segundos ao acordar). Melhor que Render Free, mas não é 24h quente sem `min-instances=1` (aí pode sair do grátis).
- Uso pessoal de bancada costuma caber na cota free.

## Testar se a memória grava

1. Abra a URL do Cloud Run
2. Resolva um caso / salve perfil
3. No console: Cloud Storage → bucket → pasta `jarvis/`
4. Deve aparecer `brain/learning.db`, `cases/`, `uploads/`

## Migração local → bucket

```bash
export GCS_BUCKET=seu-bucket
export JARVIS_DATA_DIR=./data
.venv/bin/python -c "from agent.gcs_sync import push_all; print(push_all())"
```
