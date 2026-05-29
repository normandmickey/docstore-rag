#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="norm@178.156.201.237"
REMOTE_CHECKOUT="/home/norm/sites/docstore_checkout"
REMOTE_DEPLOY_SCRIPT="/home/norm/bin/deploy-docstore"
LOCAL_REPO="/home/pi/.openclaw/workspace/projects/docstore-rag"

log() {
  printf '[deploy-docstore-vps] %s\n' "$*"
}

if [ ! -d "$LOCAL_REPO/.git" ]; then
  log "Local repo not found at $LOCAL_REPO"
  exit 1
fi

cd "$LOCAL_REPO"
log "Local commit $(git rev-parse --short HEAD)"

log "Pushing current branch to GitHub"
git push origin main

log "Running remote git-based deploy script"
ssh "$REMOTE_HOST" "$REMOTE_DEPLOY_SCRIPT"

log "Done"
