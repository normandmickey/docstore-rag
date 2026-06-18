# Docstore Install Guide

This guide is for bringing Docstore up on a fresh Linux server.

## What this installs

The bootstrap flow installs and starts:

- Django app (`docstore-rag`) via Gunicorn
- Celery worker
- Celery beat scheduler

By default the script writes these systemd services:

- `docstore-rag.service`
- `docstore-rag-celery.service`
- `docstore-rag-celery-beat.service`

Default Gunicorn bind target:

- `127.0.0.1:8010`

## What this guide does **not** fully provision for you

These dependencies still need to exist and be configured correctly:

- Postgres
- Redis
- nginx
- TLS/certbot
- S3-compatible object storage (recommended if you want production-style media storage)

Those are referenced through `.env` values.

## Recommended server assumptions

This guide assumes:

- Ubuntu/Debian-style Linux
- systemd available
- a non-root app user with a home directory
- a git checkout at a stable path such as:
  - `/home/<user>/sites/docstore_checkout`
- reverse proxy in front of Gunicorn

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

If you are running Postgres on the same box, install/configure Postgres too.

## Clone the repo

```bash
git clone git@github.com:normandmickey/docstore-rag.git /home/<user>/sites/docstore_checkout
cd /home/<user>/sites/docstore_checkout
```

## Create `.env`

### Core required settings

At minimum, set these:

```env
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=example.com,www.example.com,127.0.0.1,localhost
DATABASE_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/docstore_rag
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
OPENAI_API_KEY=...
GROQ_API_KEY=...
```

### Recommended storage settings

If you are using S3-compatible storage (recommended for production-style installs):

```env
S3_ENDPOINT_URL=http://127.0.0.1:9000
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=docstore-media
S3_REGION=us-east-1
S3_USE_SSL=0
```

### Common optional settings

These can be left blank unless you are using the related integrations:

- Google Drive:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
- Microsoft / SharePoint:
  - `MS_GRAPH_CLIENT_ID`
  - `MS_GRAPH_CLIENT_SECRET`
  - `MS_GRAPH_REDIRECT_URI`
- Atlassian / Confluence:
  - `ATLASSIAN_CLIENT_ID`
  - `ATLASSIAN_CLIENT_SECRET`
  - `ATLASSIAN_REDIRECT_URI`
- Dropbox:
  - `DROPBOX_CLIENT_ID`
  - `DROPBOX_CLIENT_SECRET`
  - `DROPBOX_REDIRECT_URI`
- Zoom:
  - `ZOOM_CLIENT_ID`
  - `ZOOM_CLIENT_SECRET`
  - `ZOOM_REDIRECT_URI`
- AgentMail:
  - `AGENTMAIL_API_KEY`
  - `AGENTMAIL_INBOX_ID`
- voice / support / shipping integrations as needed

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
- write systemd service units into `/etc/systemd/system`
- enable and restart app/worker/beat
- run `manage.py check`

### Default bootstrap assumptions

The script defaults to:

- `APP_ROOT=/home/$USER/sites/docstore_checkout`
- `VENV_PATH=$APP_ROOT/.venv`
- `APP_BIND=127.0.0.1:8010`

You can override those with environment variables before running the script.

## Configure nginx

You still need an nginx server block in front of Gunicorn.

Minimal example:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    location /static/ {
        alias /home/<user>/sites/docstore_checkout/staticfiles/;
    }

    location /media/ {
        alias /home/<user>/sites/docstore_checkout/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then add TLS with certbot for your chosen domain.

## Verify the install

### Service status

```bash
sudo systemctl status docstore-rag.service
sudo systemctl status docstore-rag-celery.service
sudo systemctl status docstore-rag-celery-beat.service
```

### Local health check

```bash
curl http://127.0.0.1:8010/healthz/
```

Expected result: JSON with `ok: true`.

### Web checks

Once nginx/TLS is configured:

- homepage loads
- `/healthz/` returns JSON
- login works
- dashboard works
- uploads work
- `/api/quickstart/` loads
- `/api/docs/` loads

### Worker sanity check

Upload a small document and confirm:

- an ingestion job is created
- the job moves through queued/running to ready
- chunks/facts become visible in the dashboard

## Troubleshooting

### App does not start

Check:

```bash
sudo systemctl status docstore-rag.service
journalctl -u docstore-rag.service -n 100 --no-pager
```

Common causes:
- missing `.env`
- bad `DATABASE_URL`
- missing Python dependency
- migration failure

### Celery worker is not processing jobs

Check:

```bash
sudo systemctl status docstore-rag-celery.service
journalctl -u docstore-rag-celery.service -n 100 --no-pager
```

Common causes:
- Redis unavailable
- broker/backend URL wrong
- provider/API key missing for embedding or answer tasks

### Health endpoint fails through nginx

Check:
- Gunicorn is listening on `127.0.0.1:8010`
- nginx `proxy_pass` points to the same port
- `DJANGO_ALLOWED_HOSTS` includes your domain

### Uploads or stored files break

Check:
- S3/MinIO settings are correct if using object storage
- local media path is writable if using local media

### Support/chat works poorly even though app is up

Check:
- embeddings provider key
- chat provider key
- Celery worker health
- document ingestion status
- chunk/fact visibility in document detail pages

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
