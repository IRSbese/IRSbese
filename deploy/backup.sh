#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/var/www/irsbese"
BACKUP_DIR="/var/backups/irsbese"
STAMP="$(date +%Y%m%d-%H%M%S)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
mkdir -p "$BACKUP_DIR"

python3 - "$APP_DIR/instance/irsbese.sqlite3" "$TMP_DIR/irsbese.sqlite3" <<'PY'
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
PY

if [[ -d "$APP_DIR/app/static/uploads" ]]; then
  mkdir -p "$TMP_DIR/uploads"
  cp -a "$APP_DIR/app/static/uploads/." "$TMP_DIR/uploads/"
fi

tar -czf "$BACKUP_DIR/irsbese-$STAMP.tar.gz" -C "$TMP_DIR" .
chmod 600 "$BACKUP_DIR/irsbese-$STAMP.tar.gz"
echo "Backup created: $BACKUP_DIR/irsbese-$STAMP.tar.gz"
