# Docstore Install Guide

This guide is for bringing Docstore up on a fresh Linux server.

## What this installs

- Django app (`docstore-rag`)
- Gunicorn app service
- Celery worker
- Celery beat

It does **not** fully provision these dependencies for you automatically:

- Postgres
- Redis
- nginx
- TLS/certbot
- MinIO/S3-compatible object storage

Those still need to exist and be configured in `.env`.

## Recommended baseline packages

Install the basics first:

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  build-essential \
  libpq-dev \
  redis-server \
  nginx
```

If you are using Postgres locally on the same server, install/configure Postgres too.

## Clone the repo

```bash
git clone git@github.com:normandmickey/docstore-rag.git /home/<user>/sites/docstore_checkout
cd /home/<user>/sites/docstore_checkout
```

## Create `.env`

At minimum, configure:

```env
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=ragbee.ai,www.ragbee.ai,127.0.0.1,localhost
DATABASE_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/docstore_rag
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
OPENAI_API_KEY=...
GROQ_API_KEY=...
S3_ENDPOINT_URL=http://127.0.0.1:9000
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=docstore-media
```

Also add OAuth/env settings as needed for:

- Google Drive
- Microsoft / SharePoint
- Zoom
- AgentMail
- voice integrations

## Bootstrap the app services

Run:

```bash
chmod +x scripts/bootstrap-docstore-server.sh
./scripts/bootstrap-docstore-server.sh
```

This script will:

- create `.venv` if needed
- install requirements
- run migrations
- collect static
- write systemd service units
- enable and restart gunicorn/celery/celery-beat
- run `manage.py check`

## Configure nginx

You still need an nginx server block in front of Gunicorn.

Example upstream target:

- `127.0.0.1:8010`

You should also enable TLS with certbot for your chosen domain.

## Verify

Once nginx is configured:

- app homepage loads
- `/healthz` returns JSON
- login works
- dashboard works
- uploads work
- `/api/quickstart/` loads
- `/api/docs/` loads

## Notes

- Keep `.env` out of destructive syncs.
- Keep `.venv` local to the server.
- Use git-based deploys after bootstrap.
- Keep `docstore-bot-runner` and `docstore-voice-agent` as separate services.

## Related docs

- `DEPLOY.md` — current production deploy model
- `README.md` — product + API overview
- `/api/quickstart/` — practical API examples
- `/api/docs/` — Swagger/OpenAPI reference
