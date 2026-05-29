# Docstore Deploy

## Current production deploy model

Docstore now deploys from a **real checkout-style tree on the VPS**:

- Checkout: `/home/norm/sites/docstore_checkout`
- Live app path: `/home/norm/sites/docstore_rag`
- Deploy script: `/home/norm/bin/deploy-docstore`

`/home/norm/sites/docstore_rag` should remain a symlink to the checkout.

## Why

This avoids drift from copy-only runtime deploys and keeps one canonical app tree on the VPS.
It also keeps deploy logic outside the checkout so `git clean` cannot remove the script.

## Runtime state that must be preserved

These are local/runtime-owned and should not be replaced by syncs or git clean:

- `.env`
- `.venv/`

They live in the checkout path and are intentionally excluded from sync/deploy updates.

## Current deploy flow

Because VPS GitHub SSH auth is not yet working for this repo, the current safe flow is:

1. Commit locally in `projects/docstore-rag`
2. Sync local repo contents to VPS checkout with rsync, excluding `.env` and `.venv`
3. Run `/home/norm/bin/deploy-docstore`

Example sync shape from the Pi:

```bash
rsync -av --delete \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'tmp_inspect_candidates.py' \
  /home/pi/.openclaw/workspace/projects/docstore-rag/ \
  norm@178.156.201.237:/home/norm/sites/docstore_checkout/
```

Then on the VPS:

```bash
/home/norm/bin/deploy-docstore
```

## Deploy script responsibilities

The deploy script should:

- verify checkout exists
- verify `.venv` exists
- verify `.env` exists
- install requirements
- apply migrations
- collect static
- reload gunicorn
- restart the celery worker
- run `manage.py check`

## Future improvement

Once VPS GitHub SSH auth is fixed, switch to true VPS-side git updates:

- `git fetch origin`
- `git checkout main`
- `git reset --hard origin/main`
- `/home/norm/bin/deploy-docstore`

That should become the preferred steady-state model.
