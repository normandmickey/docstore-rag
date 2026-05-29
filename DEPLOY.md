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

Docstore now supports a proper git-based VPS deploy flow.

1. Commit locally in `projects/docstore-rag`
2. Push `main` to GitHub
3. Run `/home/norm/bin/deploy-docstore` on the VPS

From the Pi repo, the helper script is:

```bash
./scripts/deploy-docstore-vps.sh
```

That script:
- pushes local `main` to GitHub
- SSHes to the VPS
- runs the remote git-based deploy script

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
