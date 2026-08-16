#!/bin/bash
# SIPV Server Installation Script
# Run as: sudo bash install.sh

set -e

echo "=== Installing SIPV dependencies ==="

# System packages
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3.14-venv python3-pip \
  postgresql postgresql-contrib \
  nginx \
  redis-server \
  build-essential \
  git curl wget

# Asterisk (from source for latest + ARI support)
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  asterisk \
  asterisk-config \
  asterisk-modules

echo "=== Creating sipv PostgreSQL user and database ==="
sudo -u postgres psql -c "CREATE USER sipv WITH PASSWORD 'sipv_change_me';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE sipv OWNER sipv;" 2>/dev/null || true

echo "=== Creating Python venv ==="
python3 -m venv /home/sipv/sipv/backend/venv
/home/sipv/sipv/backend/venv/bin/pip install -r /home/sipv/sipv/backend/requirements.txt

echo "=== Enabling services ==="
systemctl enable postgresql redis-server nginx
systemctl start postgresql redis-server

echo "=== Done! ==="
echo "Next: copy .env.example to .env and configure, then run alembic upgrade head"
