#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# ASHA Worker Copilot — EC2 Setup Script
# Amazon Linux 2023 | t3.small recommended
#
# Run as root on a fresh EC2 instance:
#   sudo bash setup_ec2.sh
#
# NOTE: provision_ec2.py runs this automatically via User Data.
#       Use this script for manual (re-)setup after SSH-ing into the instance.
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_DIR="/opt/asha-copilot"
REPO="https://github.com/MitraKin/asha-worker-copilot.git"

echo "=================================================="
echo "  ASHA Worker Copilot — EC2 Deployment Setup"
echo "=================================================="

# ── 1. System update ──────────────────────────────────────────────────────────
echo "[1/8] Updating system packages..."
dnf update -y
dnf install -y git nginx python3.11 python3.11-pip nodejs npm

# Set python3 default
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 || true

# ── 2. Clone / pull repository ────────────────────────────────────────────────
echo "[2/8] Setting up application directory..."
if [ -d "$APP_DIR/.git" ]; then
    echo "  Repo already cloned — pulling latest..."
    cd "$APP_DIR" && git pull origin master
else
    echo "  Cloning from GitHub..."
    rm -rf "$APP_DIR"
    git clone "$REPO" "$APP_DIR"
fi
chown -R ec2-user:ec2-user "$APP_DIR"

# ── 3. Production .env (IAM Instance Role handles AWS credentials) ────────────
echo "[3/8] Setting up production config..."
if [ ! -f "$APP_DIR/backend/.env" ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > "$APP_DIR/backend/.env" << ENVEOF
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=$SECRET
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_API_KEY=
BEDROCK_KNOWLEDGE_BASE_ID=
BEDROCK_DATA_SOURCE_ID=
COGNITO_USER_POOL_ID=us-east-1_PfhijEVpM
COGNITO_CLIENT_ID=6pdhbp4n418ubbp61t9ln5ikpm
COGNITO_REGION=us-east-1
DYNAMO_PATIENTS_TABLE=asha-patients
DYNAMO_ASSESSMENTS_TABLE=asha-assessments
DYNAMO_VACCINATIONS_TABLE=asha-vaccinations
DYNAMO_SESSIONS_TABLE=asha-sessions
S3_GUIDELINES_BUCKET=asha-copilot-guidelines
S3_AUDIO_BUCKET=asha-copilot-audio
ENVEOF
    echo "  .env created"
else
    echo "  .env already exists — keeping"
fi

# ── 4. Backend setup ──────────────────────────────────────────────────────────
echo "[4/8] Setting up FastAPI backend..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ── 5. systemd service for FastAPI ────────────────────────────────────────────
echo "[5/8] Creating systemd service..."
cat > /etc/systemd/system/asha-backend.service << 'SVCEOF'
[Unit]
Description=ASHA Worker Copilot FastAPI Backend
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/asha-copilot/backend
EnvironmentFile=/opt/asha-copilot/backend/.env
ExecStart=/opt/asha-copilot/backend/venv/bin/gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --timeout 120 --access-logfile /var/log/asha-backend-access.log --error-logfile /var/log/asha-backend-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# ── 6. Frontend build ─────────────────────────────────────────────────────────
echo "[6/8] Building React frontend..."
cd "$APP_DIR/frontend"
npm ci
npm run build

# ── 7. Nginx configuration ────────────────────────────────────────────────────
echo "[7/8] Configuring Nginx..."
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/asha-copilot.conf
rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
nginx -t

# ── 8. Enable and start services ──────────────────────────────────────────────
echo "[8/8] Starting services..."
systemctl daemon-reload
systemctl enable --now asha-backend
systemctl enable --now nginx

echo ""
echo "=================================================="
echo "  Setup Complete!"
echo "=================================================="
echo ""
echo "  Status checks:"
echo "    systemctl status asha-backend"
echo "    systemctl status nginx"
echo ""
echo "  Logs:"
echo "    journalctl -u asha-backend -f"
echo "    tail -f /var/log/asha-backend-error.log"
echo ""
echo "  App URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
