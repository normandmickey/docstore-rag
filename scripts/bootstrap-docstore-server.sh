#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-$USER}"
APP_ROOT="${APP_ROOT:-/home/$APP_USER/sites/docstore_checkout}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_PATH="${VENV_PATH:-$APP_ROOT/.venv}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
APP_SERVICE="${APP_SERVICE:-docstore-rag.service}"
CELERY_SERVICE="${CELERY_SERVICE:-docstore-rag-celery.service}"
CELERY_BEAT_SERVICE="${CELERY_BEAT_SERVICE:-docstore-rag-celery-beat.service}"
APP_BIND="${APP_BIND:-127.0.0.1:8010}"

log() {
  printf '[bootstrap-docstore-server] %s\n' "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { log "Missing required command: $1"; exit 1; }
}

require_cmd git
require_cmd "$PYTHON_BIN"

if [ ! -d "$APP_ROOT/.git" ]; then
  log "Expected git checkout at $APP_ROOT"
  log "Clone the repo first, for example:"
  log "  git clone git@github.com:normandmickey/docstore-rag.git $APP_ROOT"
  exit 1
fi

cd "$APP_ROOT"

if [ ! -d "$VENV_PATH" ]; then
  log "Creating virtual environment at $VENV_PATH"
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

log "Installing Python requirements"
"$VENV_PATH/bin/pip" install --upgrade pip wheel
"$VENV_PATH/bin/pip" install -r requirements.txt

if [ ! -f "$APP_ROOT/.env" ]; then
  log "No .env found at $APP_ROOT/.env"
  log "Create it before starting services."
fi

log "Writing systemd unit templates to $SYSTEMD_DIR"
sudo tee "$SYSTEMD_DIR/$APP_SERVICE" >/dev/null <<EOF
[Unit]
Description=Docstore Django app
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_ROOT
EnvironmentFile=$APP_ROOT/.env
ExecStart=$VENV_PATH/bin/gunicorn config.wsgi:application --bind $APP_BIND --workers 3 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$SYSTEMD_DIR/$CELERY_SERVICE" >/dev/null <<EOF
[Unit]
Description=Docstore Celery worker
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_ROOT
EnvironmentFile=$APP_ROOT/.env
ExecStart=$VENV_PATH/bin/celery -A config worker --loglevel=INFO --queues=docstore
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$SYSTEMD_DIR/$CELERY_BEAT_SERVICE" >/dev/null <<EOF
[Unit]
Description=Docstore Celery beat
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_ROOT
EnvironmentFile=$APP_ROOT/.env
ExecStart=$VENV_PATH/bin/celery -A config beat --loglevel=INFO --pidfile=/tmp/docstore-rag-celery-beat.pid --schedule=$APP_ROOT/celerybeat-schedule
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

log "Running migrations"
"$VENV_PATH/bin/python" manage.py migrate

log "Collecting static files"
"$VENV_PATH/bin/python" manage.py collectstatic --noinput

log "Reloading systemd"
sudo systemctl daemon-reload

log "Enabling services"
sudo systemctl enable "$APP_SERVICE" "$CELERY_SERVICE" "$CELERY_BEAT_SERVICE"

log "Starting services"
sudo systemctl restart "$APP_SERVICE" "$CELERY_SERVICE" "$CELERY_BEAT_SERVICE"

log "Running Django check"
"$VENV_PATH/bin/python" manage.py check

log "Done. Next: configure nginx + TLS for your chosen domain, then verify /healthz through the proxy."
