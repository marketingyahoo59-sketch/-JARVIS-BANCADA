#!/usr/bin/env bash
# Roda NO SERVIDOR (Ubuntu). Substitui OrganizaZap pelo JARVIS de Bancada.
set -euo pipefail

APP_DIR=/opt/jarvis-bancada
DOMAIN="${DOMAIN:-34-122-2-87.sslip.io}"
PORT=3847

echo "==> Parando serviços antigos (OrganizaZap / uvicorn / etc.)"
systemctl stop organizazap 2>/dev/null || true
systemctl disable organizazap 2>/dev/null || true
systemctl stop assistente-financeiro 2>/dev/null || true
pkill -f 'uvicorn' 2>/dev/null || true
pkill -f 'gunicorn' 2>/dev/null || true
pkill -f 'organiza' 2>/dev/null || true

echo "==> Dependências"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip nginx

echo "==> App em $APP_DIR"
mkdir -p "$APP_DIR"
# espera o código já ter sido copiado para /tmp/jarvis-src
if [[ -d /tmp/jarvis-src ]]; then
  rsync -a --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude 'data/cases' \
    --exclude 'data/uploads' --exclude '.git' \
    /tmp/jarvis-src/ "$APP_DIR/"
fi

cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

mkdir -p data/cases data/uploads data/docs data/failures
if [[ -f /tmp/jarvis.env ]]; then
  cp /tmp/jarvis.env "$APP_DIR/.env"
fi

echo "==> systemd"
cat >/etc/systemd/system/jarvis-bancada.service <<EOF
[Unit]
Description=JARVIS de Bancada (Streamlit)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP_DIR/.venv/bin/streamlit run app.py --server.port $PORT --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable jarvis-bancada
systemctl restart jarvis-bancada

echo "==> nginx"
cat >/etc/nginx/sites-available/jarvis-bancada <<EOF
server {
    listen 80;
    listen 443 ssl;
    server_name $DOMAIN 34.122.2.87;

    # se não houver cert, nginx ainda sobe no 80
    ssl_certificate     /etc/nginx/ssl/jarvis.crt;
    ssl_certificate_key /etc/nginx/ssl/jarvis.key;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
    }
}
EOF

mkdir -p /etc/nginx/ssl
if [[ ! -f /etc/nginx/ssl/jarvis.crt ]]; then
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout /etc/nginx/ssl/jarvis.key \
    -out /etc/nginx/ssl/jarvis.crt \
    -subj "/CN=$DOMAIN" 2>/dev/null || true
fi

# se SSL self-signed falhar no listen 443, fallback só HTTP
if ! nginx -t 2>/dev/null; then
  cat >/etc/nginx/sites-available/jarvis-bancada <<EOF
server {
    listen 80 default_server;
    server_name $DOMAIN 34.122.2.87 _;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
    }
}
EOF
fi

ln -sfn /etc/nginx/sites-available/jarvis-bancada /etc/nginx/sites-enabled/jarvis-bancada
rm -f /etc/nginx/sites-enabled/default
# remove site antigo se existir
rm -f /etc/nginx/sites-enabled/organizazap /etc/nginx/sites-enabled/assistente* 2>/dev/null || true
nginx -t
systemctl reload nginx

echo "==> OK"
systemctl --no-pager status jarvis-bancada | head -20
curl -sS -m 5 -o /dev/null -w "local:%{http_code}\n" http://127.0.0.1:$PORT/ || true
echo "Abra: https://$DOMAIN  ou  http://$DOMAIN"
