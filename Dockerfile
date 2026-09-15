# JARVIS — deploy no Railway (rápido + memória permanente)

FROM python:3.12-slim

WORKDIR /app

# Padrão Cloud Run (disco tmp + sync GCS). No Railway sobrescreva JARVIS_DATA_DIR=/data
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    JARVIS_DATA_DIR=/tmp/jarvis-data \
    JARVIS_TTS=edge

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/jarvis-data /data

EXPOSE 8080

CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
