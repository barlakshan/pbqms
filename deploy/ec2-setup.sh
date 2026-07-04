#!/bin/bash
set -euo pipefail

# Ubuntu EC2 deployment script for PBQMS
# Run as sudo

APP_DIR=/home/ubuntu/pbqms
REPO_URL=${REPO_URL:-https://github.com/your-org/pbqms.git}
BRANCH=${BRANCH:-main}
PYTHON_BIN=/usr/bin/python3

apt-get update
apt-get install -y python3-pip python3-venv nginx git curl build-essential libmysqlclient-dev default-libmysqlclient-dev pkg-config

if [ ! -d "$APP_DIR" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  cd "$APP_DIR"
  git pull origin "$BRANCH" || true
fi

cd "$APP_DIR"
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p static/qrcodes
cp .env.example .env

cat > /etc/nginx/sites-available/pbqms <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location /static/ {
        alias /home/ubuntu/pbqms/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

ln -sf /etc/nginx/sites-available/pbqms /etc/nginx/sites-enabled/pbqms
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

cat > /etc/systemd/system/pbqms.service <<'EOF'
[Unit]
Description=PBQMS Flask Application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/pbqms
Environment=PATH=/home/ubuntu/pbqms/venv/bin
Environment=FLASK_ENV=production
ExecStart=/home/ubuntu/pbqms/venv/bin/gunicorn --config /home/ubuntu/pbqms/gunicorn.conf.py wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pbqms
systemctl restart pbqms

echo "EC2 deployment setup completed."
echo "Next steps:"
echo "  sudo nano /home/ubuntu/pbqms/.env"
echo "  sudo systemctl status pbqms"
echo "  sudo journalctl -u pbqms -f"
