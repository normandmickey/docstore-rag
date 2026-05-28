# Docstore RAG

A multi-tenant document storage, retrieval, and chat service for RAG workflows, built with Django for admin visibility and operational control.

## Current Status

Docstore is live at:

- `https://docstore.oddsmith.net`

Current stack and behavior are now beyond the initial scaffold stage:

- Django app with signup/login/logout
- tenant + workspace onboarding
- dashboard-based file uploads
- async ingestion with Celery + Redis
- Postgres + pgvector chunk storage
- OpenAI embeddings
- workspace search
- basic dashboard chat with documents
- duplicate detection + versioning
- SharePoint connector foundation scaffolded

## What Works Now

### Authentication and onboarding
- user signup/login/logout
- automatic tenant + default workspace bootstrap
- workspace creation and switching from the dashboard
- dashboard API key management (create + revoke)

### Document ingestion
- dashboard upload flow
- local filesystem storage fallback in production when S3/MinIO is not configured
- per-document ingestion jobs via Celery
- document status tracking in the dashboard
- failed documents hidden from the main dashboard list

### Supported file types
- PDF via `PyMuPDF`
- DOCX via `python-docx`
- Markdown (`.md`)
- plain text (`.txt`)
- basic HTML ingestion

### Retrieval and chat
- embeddings stored in Postgres via pgvector
- `/api/v1/search/` uses vector similarity search
- `/api/v1/chat/` returns answer + cited source chunks
- dashboard “chat with documents” UI retrieves chunks and generates an answer with source context

### Duplicate/version handling
- exact duplicate uploads in the same workspace are skipped using content hash comparison
- same filename + changed content becomes a new `DocumentVersion`
- dashboard shows version count and latest version number

### Connector groundwork
- `connectors` app exists
- SharePoint connector models/admin/migration exist
- Microsoft Graph helper exists
- manual SharePoint sync command scaffold exists
- per-user Microsoft OAuth account connection scaffold exists

## Architecture

## Core concepts
- **Tenant**: top-level account/org boundary
- **Workspace**: logical knowledge base inside a tenant
- **Collection**: optional namespace/tag within a workspace
- **Document**: stored source file and document-level metadata
- **DocumentVersion**: version history for a logical document
- **Chunk**: retrievable text unit with embedding
- **IngestionJob**: async parse/chunk/embed job
- **ExternalAccount**: user-owned OAuth-linked external provider account (currently Microsoft scaffold)
- **Connector**: sync configuration for external systems like SharePoint

## App layout
- `control` — auth flow, tenants, workspaces, API keys, external accounts
- `documents` — document records, versions, upload handling, duplicate/version logic
- `ingestion` — parsing, chunking, embeddings, Celery jobs
- `retrieval` — vector search, answer assembly, dashboard chat
- `audit` — retrieval logging
- `connectors` — SharePoint connector models, Graph helper, sync runs, bindings

## Key implementation decisions
- use Postgres + pgvector as the primary retrieval store
- use OpenAI embeddings (`text-embedding-3-large` by default)
- keep original files out of Postgres
- prefer local filesystem storage until a real S3/MinIO endpoint exists
- queue ingestion one document/job at a time through Celery
- isolate docstore Celery onto its own queue (`docstore`)
- enqueue ingestion only after DB transaction commit
- use content-hash-aware duplicate detection instead of filename-only logic

## Important Routes

### Web
- `/`
- `/signup/`
- `/login/`
- `/logout/`
- `/dashboard/`
- `/admin/`
- `/healthz/`
- `/connect/microsoft/`
- `/connect/microsoft/callback/`

### API
- `POST /api/v1/documents/`
- `POST /api/v1/documents/delete/`
- `POST /api/v1/documents/restore/`
- `POST /api/v1/documents/purge/`
- `POST /api/v1/urls/ingest/`
- `POST /api/v1/search/`
- `POST /api/v1/chat/`

## Key Models

### control
- `Tenant`
- `Workspace`
- `TenantMembership`
- `APIKey`
- `ExternalAccount`

### documents
- `Document`
- `DocumentVersion`
- `Chunk`

### ingestion
- `IngestionJob`

### connectors
- `Connector`
- `ConnectorSyncRun`
- `ExternalDocumentBinding`

## Environment Notes

### OpenAI
Required for embeddings and current answer generation:

```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_EMBEDDING_MODEL=text-embedding-3-large
DEFAULT_CHAT_MODEL=gpt-4.1-mini
```

### Storage
If no real S3/MinIO endpoint is configured, the app falls back to local filesystem storage.

### Celery
Docstore uses its own queue:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Worker should consume the `docstore` queue.

### Microsoft / SharePoint OAuth scaffold
Not fully configured yet in production. When resumed, these env vars are expected:

```env
MS_GRAPH_CLIENT_ID=...
MS_GRAPH_CLIENT_SECRET=...
MS_GRAPH_REDIRECT_URI=https://docstore.oddsmith.net/connect/microsoft/callback/
MS_GRAPH_TENANT_ID=common
MS_GRAPH_SCOPES=openid profile email offline_access Files.Read Sites.Read.All User.Read
```

### Microsoft app registration setup
Use this when resuming user-owned SharePoint connections.

#### 1. Create the app registration
In Azure / Microsoft Entra:

- go to `Microsoft Entra ID`
- go to `App registrations`
- click `New registration`

Recommended values:

- **Name:** `docstore-rag`
- **Supported account types:**
  - use **Accounts in any organizational directory and personal Microsoft accounts** if you want broad compatibility
  - use an org-only option if this should only work for one Microsoft 365 tenant
- **Redirect URI:**
  - Platform: `Web`
  - URI: `https://docstore.oddsmith.net/connect/microsoft/callback/`

After creation, copy:

- **Application (client) ID** → `MS_GRAPH_CLIENT_ID`
- **Directory (tenant) ID** → use as `MS_GRAPH_TENANT_ID` if you want tenant-specific auth
  - otherwise set `MS_GRAPH_TENANT_ID=common` for multi-tenant behavior

#### 2. Create the client secret
In the app registration:

- go to `Certificates & secrets`
- click `New client secret`
- create one and copy the **Value** immediately

Use that value as:

- `MS_GRAPH_CLIENT_SECRET`

Important: use the **secret value**, not the secret ID.

#### 3. Configure authentication
In the app registration:

- go to `Authentication`
- confirm the redirect URI exists exactly as:
  - `https://docstore.oddsmith.net/connect/microsoft/callback/`

No SPA/mobile setup is needed for the current server-side auth-code flow.

#### 4. Add Microsoft Graph API permissions
In the app registration:

- go to `API permissions`
- click `Add a permission`
- choose `Microsoft Graph`
- choose `Delegated permissions`

Add:

- `openid`
- `profile`
- `email`
- `offline_access`
- `User.Read`
- `Files.Read`
- `Sites.Read.All`

If needed for your tenant, grant admin consent after adding permissions.

#### 5. Set the production env vars
Add these to the VPS `.env` for docstore:

```env
MS_GRAPH_CLIENT_ID=YOUR_CLIENT_ID
MS_GRAPH_CLIENT_SECRET=YOUR_SECRET_VALUE
MS_GRAPH_REDIRECT_URI=https://docstore.oddsmith.net/connect/microsoft/callback/
MS_GRAPH_TENANT_ID=common
MS_GRAPH_SCOPES=openid profile email offline_access Files.Read Sites.Read.All User.Read
```

#### 6. Restart the app after updating env
After editing `/home/norm/sites/docstore_rag/.env` on the VPS, restart:

```bash
sudo systemctl restart docstore-rag.service docstore-rag-celery.service
```

## SharePoint Status

SharePoint support is partially scaffolded, not finished.

### Already built
- connector models and admin
- Graph helper
- manual sync command scaffold
- per-user Microsoft account connection scaffold

### Still needed
- real Azure app registration/config in production
- user-facing site/drive/folder picker
- token refresh handling
- user-token-based SharePoint browsing/sync
- scheduled/incremental sync
- cleaner connector UX in dashboard

## Operational Notes
- production deploy path uses Pi -> VPS rsync
- `.env` is intentionally excluded from deploy sync
- generated vectors live in Postgres, not SQLite
- chat quality depends on extraction quality + chunk quality
- PDF parsing is now real; OCR/layout-heavy docs are still not a focus yet

## API keys

Dashboard users can now create and revoke API keys from:

- `/dashboard/api-keys/`

Current behavior:
- raw key is shown once at creation time
- only the prefix + SHA-256 hash are stored
- keys can be scoped to current workspace or whole tenant
- revoke disables a key without deleting the DB record
- helper exists for Bearer-token lookup and `last_used_at` updates (`control/api_auth.py`)

Current behavior now:
- unauthenticated API requests must provide a Bearer API key
- tenant mismatch is rejected
- workspace-scoped keys can only access their workspace
- successful API-key lookups update `last_used_at`

Current limitation:
- not every future endpoint is wired yet; new endpoints should use the same guard pattern in `control/api_guard.py`

## API examples

All unauthenticated API requests should include a Bearer API key:

```http
Authorization: Bearer ds_...
```

### Search

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/search/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "query": "What does this workspace say about authentication?",
    "top_k": 5
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/search/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "query": "What does this workspace say about authentication?",
        "top_k": 5,
    },
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

### Chat

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/chat/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "question": "Summarize the policy described in these docs.",
    "top_k": 5
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/chat/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "question": "Summarize the policy described in these docs.",
        "top_k": 5,
    },
    timeout=120,
)
resp.raise_for_status()
data = resp.json()
print(data["answer"])
for source in data["sources"]:
    print(source["document"], source["chunk_index"])
```

Optional document-scoped chat:

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/chat/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "question": "What does this specific document say about onboarding?",
    "document_id": 42,
    "top_k": 5
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/chat/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "question": "What does this specific document say about onboarding?",
        "document_id": 42,
        "top_k": 5,
    },
    timeout=120,
)
resp.raise_for_status()
print(resp.json())
```

### URL ingest

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/urls/ingest/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "urls": [
      "https://example.com/docs/start",
      "https://example.com/help/article"
    ],
    "collection": "docs",
    "crawl_mode": "single",
    "max_pages": 10
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/urls/ingest/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "urls": [
            "https://example.com/docs/start",
            "https://example.com/help/article",
        ],
        "collection": "docs",
        "crawl_mode": "single",
        "max_pages": 10,
    },
    timeout=180,
)
resp.raise_for_status()
print(resp.json())
```

### Document delete / restore / purge

Soft delete:

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/documents/delete/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "document_ids": [12, 13]
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/documents/delete/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "document_ids": [12, 13],
    },
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

Restore:

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/documents/restore/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "document_ids": [12, 13]
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/documents/restore/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "document_ids": [12, 13],
    },
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

Purge:

```bash
curl -X POST https://docstore.oddsmith.net/api/v1/documents/purge/ \
  -H "Authorization: Bearer ds_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "workspace_id": 1,
    "document_ids": [12, 13]
  }'
```

```python
import requests

resp = requests.post(
    "https://docstore.oddsmith.net/api/v1/documents/purge/",
    headers={
        "Authorization": "Bearer ds_YOUR_KEY",
        "Content-Type": "application/json",
    },
    json={
        "tenant_id": 1,
        "workspace_id": 1,
        "document_ids": [12, 13],
    },
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

## Good Next Steps
- add document detail + reingest flow
- add SharePoint site/drive/folder picker using connected Microsoft accounts
- improve token handling and connector UX
- extend parser coverage further only as needed
