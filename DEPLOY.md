# Docstore Deploy

## Current production deploy model

Docstore deploys from a **real checkout-style tree on the VPS**:

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

Docstore currently uses a **git-based Pi → VPS deploy flow**.

1. Commit locally in `projects/docstore-rag`
2. Push `main` to GitHub
3. Run `/home/norm/bin/deploy-docstore` on the VPS

From the Pi repo, the helper script is:

```bash
./scripts/deploy-docstore-vps.sh
```

That helper:
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
- restart the Celery worker
- run `manage.py check`

## Production notes

Docstore is the control plane for:
- tenant/workspace management
- retrieval/chat APIs
- support settings and support data
- chatbot integrations/definitions/bindings
- voice transcript ingest

Separate runtimes should stay outside the Django app runtime:
- `docstore-bot-runner` for Telegram/Discord execution
- `docstore-voice-agent` for realtime Twilio voice execution

That separation is intentional and should be preserved during deploy/design changes.

## Important operational boundaries

- Keep `.env` excluded from destructive syncs.
- Keep the VPS checkout as the source of truth for runtime code.
- Keep long-running bot/voice processes in their own services rather than folding them into gunicorn/Django.
- Keep Postgres as the backing store for embeddings, retrieval data, support data, and chatbot state.

## Future improvement

Once VPS GitHub SSH auth is fixed cleanly, switch to true VPS-side git updates:

- `git fetch origin`
- `git checkout main`
- `git reset --hard origin/main`
- `/home/norm/bin/deploy-docstore`

That should become the preferred steady-state model.
