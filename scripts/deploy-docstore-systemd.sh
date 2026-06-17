#!/usr/bin/env bash
set -euo pipefail

CHECKOUT="/home/norm/sites/docstore_checkout"
APP_LINK="/home/norm/sites/docstore_rag"
VENV="$CHECKOUT/.venv"
ENV_FILE="$CHECKOUT/.env"
BRANCH="main"

APP_SERVICE="docstore-rag.service"
CELERY_SERVICE="docstore-rag-celery.service"
CELERY_BEAT_SERVICE="docstore-rag-celery-beat.service"

LOCAL_HEALTH_URL="http://127.0.0.1:8010/healthz"

log() {
  printf '[deploy-docstore] %s\n' "$*"
}

require_file() {
  local path="$1"
  local label="$2"
  if [ ! -e "$path" ]; then
    log "Missing $label at $path"
    exit 1
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log "Missing required command: $1"
    exit 1
  }
}

require_cmd git
require_cmd curl
require_cmd systemctl

require_file "$CHECKOUT" "checkout directory"
cd "$CHECKOUT"

if [ ! -d .git ]; then
  log "Missing git checkout at $CHECKOUT"
  exit 1
fi

require_file "$VENV/bin/python" "virtualenv python"
require_file "$ENV_FILE" ".env file"

log "Fetching latest repo state"
git fetch --quiet origin

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
  log "Checking out $BRANCH"
  git checkout -q "$BRANCH"
fi

LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  log "Updating checkout to ${REMOTE_HEAD:0:7}"
else
  log "Checkout already at latest origin/$BRANCH"
fi

git reset --hard -q "origin/$BRANCH"
git clean -fd -q -e .venv -e .env

if [ ! -L "$APP_LINK" ] || [ "$(readlink -f "$APP_LINK")" != "$(readlink -f "$CHECKOUT")" ]; then
  log "Ensuring runtime symlink points to checkout"
  rm -rf "$APP_LINK"
  ln -sfn "$CHECKOUT" "$APP_LINK"
fi

log "Installing requirements"
"$VENV/bin/python" -m pip install -q -r requirements.txt

log "Applying migrations"
"$VENV/bin/python" manage.py migrate --noinput

log "Collecting static files"
"$VENV/bin/python" manage.py collectstatic --noinput --verbosity 0

log "Running Django system checks"
"$VENV/bin/python" manage.py check

log "Restarting services"
sudo systemctl restart "$APP_SERVICE"
sudo systemctl restart "$CELERY_SERVICE"
sudo systemctl restart "$CELERY_BEAT_SERVICE"

log "Verifying services are active"
systemctl is-active --quiet "$APP_SERVICE" || {
  log "$APP_SERVICE is not active"
  sudo systemctl status --no-pager "$APP_SERVICE" || true
  exit 1
}
systemctl is-active --quiet "$CELERY_SERVICE" || {
  log "$CELERY_SERVICE is not active"
  sudo systemctl status --no-pager "$CELERY_SERVICE" || true
  exit 1
}
systemctl is-active --quiet "$CELERY_BEAT_SERVICE" || {
  log "$CELERY_BEAT_SERVICE is not active"
  sudo systemctl status --no-pager "$CELERY_BEAT_SERVICE" || true
  exit 1
}

log "Checking local health endpoint"
curl --fail --silent --show-error "$LOCAL_HEALTH_URL" >/tmp/docstore-health.out
sed -n '1,20p' /tmp/docstore-health.out

DEPLOYED_HEAD="$(git rev-parse --short HEAD)"
log "Deploy complete at commit $DEPLOYED_HEAD"
