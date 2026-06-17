# Docstore Deployment Runbook

## Normal deploy

From the local/Pi repo:

```bash
cd /home/pi/.openclaw/workspace/projects/docstore-rag
git status
git add ...
git commit -m "your message"
git push origin main
./scripts/deploy-docstore-vps.sh
```

That helper script:
- pushes `main` to GitHub
- SSHes to `docstore-vps`
- runs `/home/norm/bin/deploy-docstore`

## What the VPS deploy does

The live VPS deploy script now:

1. fetches the latest code into `/home/norm/sites/docstore_checkout`
2. hard-resets to `origin/main`
3. preserves `.env` and `.venv`
4. ensures `/home/norm/sites/docstore_rag` points to the checkout
5. installs requirements
6. runs migrations
7. runs collectstatic
8. runs Django checks
9. restarts:
   - `docstore-rag.service`
   - `docstore-rag-celery.service`
   - `docstore-rag-celery-beat.service`
10. verifies those services are active
11. checks `http://127.0.0.1:8010/healthz/`

## Fast health checks

### Local on the VPS

```bash
curl -i http://127.0.0.1:8010/healthz/
```

Expected response:

- `200 OK`
- JSON body:

```json
{"ok": true, "service": "docstore-rag"}
```

### Public

```bash
curl -i https://docstore.oddsmith.net/healthz/
```

Expected response:

- `200 OK`
- same JSON body

## Useful service checks

### Service status

```bash
systemctl status docstore-rag.service
systemctl status docstore-rag-celery.service
systemctl status docstore-rag-celery-beat.service
```

### Quick active-state check

```bash
systemctl is-active docstore-rag.service docstore-rag-celery.service docstore-rag-celery-beat.service
```

Expected:
- all services report `active`

### Recent logs

```bash
sudo journalctl -u docstore-rag.service -n 50 --no-pager
sudo journalctl -u docstore-rag-celery.service -n 50 --no-pager
sudo journalctl -u docstore-rag-celery-beat.service -n 50 --no-pager
```

## Important paths

### Code/runtime
- checkout: `/home/norm/sites/docstore_checkout`
- live app symlink: `/home/norm/sites/docstore_rag`

### Deploy script
- `/home/norm/bin/deploy-docstore`

### Health endpoints
- local: `http://127.0.0.1:8010/healthz/`
- public: `https://docstore.oddsmith.net/healthz/`

## If deploy fails

### 1. Check deploy output

Common failure points:
- Python package install
- migrations
- collectstatic
- Django checks
- service restart
- health probe

### 2. Check app logs

```bash
sudo journalctl -u docstore-rag.service -n 100 --no-pager
```

### 3. Check worker and beat logs

```bash
sudo journalctl -u docstore-rag-celery.service -n 100 --no-pager
sudo journalctl -u docstore-rag-celery-beat.service -n 100 --no-pager
```

### 4. Confirm live code version

```bash
cd /home/norm/sites/docstore_checkout
git rev-parse --short HEAD
git status --short
```

## Things not to casually break

- don’t delete `.env`
- don’t delete `.venv`
- don’t turn `/home/norm/sites/docstore_rag` into a second standalone checkout
- don’t manually start extra Celery workers outside systemd unless you mean to

## Short version

Deploy from local -> push to GitHub -> run the VPS deploy script -> if anything smells off, check `/healthz/`, `systemctl status`, and `journalctl`.
