#!/bin/bash
# Manual deploy script — run on EC2 instance to pull latest and restart
set -e
cd /opt/asha-copilot
git pull origin master
cd backend && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
sudo systemctl restart asha-backend
sudo systemctl restart nginx
echo "Deploy complete at $(date)"
