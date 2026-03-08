#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# ASHA Worker Copilot — EC2 Setup Script
# Amazon Linux 2023 | t3.small recommended
#
# Run as root on a fresh EC2 instance:
#   sudo bash setup_ec2.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "=================================================="
echo "  ASHA Worker Copilot — EC2 Deployment Setup"
echo "=================================================="

# ── 1. System update ──────────────────────────────────────────────────────────
echo "[1/7] Updating system packages..."
dnf update -y
dnf install -y git nginx python3.11 python3.11-pip nodejs npm

# Set python3 default
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# ── 2. Clone / pull repository ────────────────────────────────────────────────
echo "[2/7] Setting up application directory..."
APP_DIR="/opt/asha-copilot"
mkdir -p "$APP_DIR"

# If repo already cloned:
# cd /opt && git clone https://github.com/YOUR_REPO/asha-copilot.git
# For now, we assume files are already on instance via scp

# ── 3. Backend setup ──────────────────────────────────────────────────────────
echo "[3/7] Setting up FastAPI backend..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service for FastAPI
cat > /etc/systemd/system/asha-backend.service << 'EOF'
[Unit]
Description=ASHA Worker Copilot FastAPI Backend
After=network.target
Wants=network-online.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/asha-copilot/backend
EnvironmentFile=/opt/asha-copilot/backend/.env
ExecStart=/opt/asha-copilot/backend/venv/bin/gunicorn \
    main:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/asha-backend-access.log \
    --error-logfile /var/log/asha-backend-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ── 4. Frontend build ─────────────────────────────────────────────────────────
echo "[4/7] Building React frontend..."
cd "$APP_DIR/frontend"
npm ci
npm run build

# ── 5. Nginx configuration ────────────────────────────────────────────────────
echo "[5/7] Configuring Nginx..."
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/asha-copilot.conf

# Remove default nginx config
rm -f /etc/nginx/nginx.conf.d/default.conf 2>/dev/null || true

# Test nginx config
nginx -t

# ── 6. Enable and start services ──────────────────────────────────────────────
echo "[6/7] Starting services..."
systemctl daemon-reload
systemctl enable asha-backend
systemctl start asha-backend
systemctl enable nginx
systemctl start nginx

# ── 7. Firewall ───────────────────────────────────────────────────────────────
echo "[7/7] Configuring firewall..."
# Note: Also configure EC2 Security Group to allow inbound 80 and 443

echo ""
echo "=================================================="
echo "  ✅ Setup Complete!"
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
