#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/var/www/irsbese"
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo bash deploy/deploy_ubuntu.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx rsync
mkdir -p "$APP_DIR/instance" "$APP_DIR/app/static/uploads"
chown -R root:root "$APP_DIR"
chmod 755 "$APP_DIR" "$APP_DIR/app" "$APP_DIR/app/static"
chown -R www-data:www-data "$APP_DIR/instance" "$APP_DIR/app/static/uploads"
chmod 750 "$APP_DIR/instance" "$APP_DIR/app/static/uploads"

cd "$APP_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "ВАЖНО: задайте уникальный SECRET_KEY в $APP_DIR/.env до запуска."
fi
chown root:www-data .env
chmod 640 .env
if grep -q '^SECRET_KEY=replace-with-a-long-random-secret$' .env; then
  echo "Задайте уникальный SECRET_KEY в $APP_DIR/.env и запустите скрипт повторно."
  exit 2
fi

install -m 644 deploy/irsbese.service /etc/systemd/system/irsbese.service
install -m 644 deploy/nginx-irsbese.conf /etc/nginx/sites-available/irsbese
ln -sfn /etc/nginx/sites-available/irsbese /etc/nginx/sites-enabled/irsbese
nginx -t
systemctl daemon-reload
systemctl enable irsbese
systemctl restart irsbese
systemctl reload nginx
systemctl status irsbese --no-pager
