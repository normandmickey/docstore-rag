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
- `POST /api/v1/search/`

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

## Good Next Steps
- add document detail + reingest flow
- add `/api/v1/chat/` endpoint
- add SharePoint site/drive/folder picker using connected Microsoft accounts
- improve token handling and connector UX
- extend parser coverage further only as needed
