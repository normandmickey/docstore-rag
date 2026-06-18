# Storage Notes

## Current state

Docstore supports S3-compatible document storage via the `DocumentStorage` backend in `documents/storage.py`.

As of the current dev/test VPS setup:

- MinIO is running locally on `127.0.0.1:9000`
- the `docstore-rag` bucket exists
- Docstore is configured with:
  - `S3_ENDPOINT_URL=http://127.0.0.1:9000`
  - `S3_ACCESS_KEY=...`
  - `S3_SECRET_KEY=...`
  - `S3_BUCKET=docstore-rag`
  - `S3_REGION=us-east-1`
  - `S3_USE_SSL=0`
- the app now honors the local MinIO endpoint and uses S3-compatible storage when those env vars are present

## Important note

Historically, the storage backend had a guard that excluded `http://localhost:9000` / local MinIO-style endpoints from activating the S3 storage backend. That has now been removed so the dev/test VPS can actually use MinIO.

## Verification checklist

To confirm MinIO-backed document storage is working:

1. Verify storage mode in Django:

```bash
cd /home/norm/sites/docstore_checkout
. .venv/bin/activate
python - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from documents.models import document_storage
print('USE_S3_STORAGE=', settings.USE_S3_STORAGE)
print('storage_class=', document_storage.__class__.__name__)
print('bucket=', getattr(document_storage, 'bucket_name', None))
print('endpoint=', getattr(document_storage, 'endpoint_url', None))
PY
```

2. List MinIO objects:

```bash
mc ls --recursive local/docstore-rag | tail
```

3. Verify a real document can be opened through Django storage:

```bash
cd /home/norm/sites/docstore_checkout
. .venv/bin/activate
python - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from documents.models import Document

doc = Document.objects.exclude(file='').order_by('-id').first()
print(doc.id, doc.filename, doc.file.name)
with doc.file.open('rb') as fh:
    print(fh.read(16).hex())
print(doc.file.url)
PY
```

## What to test after storage changes

If storage config changes again, re-test:

- upload
- download/open from dashboard
- PDF ingestion
- DOCX ingestion
- URL-derived document ingest if applicable
- soft delete / restore / purge
- document detail pages
- chat/retrieval over newly uploaded docs

## Recommendation

Keep dev/test on MinIO first. Validate all storage-sensitive flows there before changing any cleaner/public Ragbee production deployment.
