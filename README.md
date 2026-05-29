# Docstore RAG

A multi-tenant document storage, retrieval, and chat service for document-grounded workflows, built with Django for admin visibility and operational control.

## Live

- `https://docstore.oddsmith.net`

## Current Status

Docstore is now well past the initial scaffold stage. The live product currently includes:

- Django auth + tenant/workspace onboarding
- dashboard uploads and URL ingestion
- async ingestion with Celery + Redis
- Postgres + pgvector storage
- OpenAI embeddings
- Groq-hosted GPT-OSS for question generation, rewrite, and chat answers
- duplicate/version handling
- soft delete / trash / restore / purge
- dashboard API key management
- document detail / facts / chunks / search inspection pages
- invite-only signup
- SharePoint OAuth foundation
- MinIO-backed production file storage

## What Works Now

### Authentication and onboarding
- user login/logout
- invite-only signup flow
- automatic tenant + default workspace bootstrap
- workspace creation and switching from the dashboard
- dashboard API key management (create + revoke)

### Document ingestion
- dashboard upload flow
- URL ingestion flow
- duplicate detection + versioning
- per-document ingestion jobs via Celery
- document/job status tracking in the dashboard
- failed docs visible separately with delete controls
- standard extractor path is production-safe and fast
- Docling exists as an experimental alternate extractor path, but is currently shelved for regular use on the VPS because runtime is too slow

### Supported file types
- PDF via `PyMuPDF` (current production path)
- DOCX via `python-docx`
- Markdown (`.md`)
- plain text (`.txt`)
- HTML via markdownified extraction

### Retrieval and chat
- pgvector-backed chunk embeddings in Postgres
- multi-signal retrieval using:
  - raw chunk embedding
  - metadata embedding
  - question embedding
  - lexical/full-text score
- strict context-only answer generation
- dashboard document-scoped search/inspection page
- dashboard chat with source-backed answers
- retrieval logging

### Facts / introspection
- extracted facts per document
- document detail pages for:
  - overview
  - facts
  - chunks
  - document-scoped search
- chunk pages show:
  - metadata text
  - question text
  - raw chunk text

## Architecture

## Core concepts
- **Tenant**: top-level org/account boundary
- **Workspace**: logical knowledge base within a tenant
- **Collection**: optional namespace/tag inside a workspace
- **Document**: stored source file + document-level metadata
- **DocumentVersion**: version history for a logical document
- **Chunk**: retrievable text unit with embeddings + metadata
- **ExtractedFact**: heuristic fact/list/policy snippets tied to a chunk
- **IngestionJob**: async parse/chunk/embed job
- **ExternalAccount**: user-owned OAuth-linked provider account (currently Microsoft scaffold)
- **Connector**: external sync configuration

## App layout
- `control` — auth flow, tenants, workspaces, API keys, external accounts, dashboard pages
- `documents` — documents, versions, chunks, facts, upload handling, duplicate/version logic
- `ingestion` — parsing, chunking, question generation, embeddings, Celery jobs
- `retrieval` — chunk retrieval, answer assembly, dashboard chat/search
- `audit` — retrieval logging
- `connectors` — SharePoint connector models, Graph helper, sync runs, bindings

## Retrieval design (current)

Docstore no longer relies on a single raw chunk embedding alone.

Each chunk can now carry multiple retrieval signals:

- `text` + `embedding`
- `metadata_text` + `metadata_embedding`
- `question_text` + `question_embedding`

### Multi-signal retrieval flow
1. rewrite the user question into a standalone question
2. embed the standalone question
3. retrieve candidates across:
   - raw chunk embeddings
   - metadata embeddings
   - question embeddings
   - Postgres full-text lexical search
4. blend those signals into one ranking score
5. do local same-document chunk expansion around the strongest hit
6. answer only from the selected context

### Why this exists
This grew out of handbook/policy retrieval problems where:
- raw embeddings alone were too fuzzy
- metadata helped but was still document-centric
- question-style retrieval text better matched how humans actually ask

## Facts layer (current)

Docstore also builds a lightweight extracted-facts layer during ingestion.

Current fact types:
- `heading`
- `list_item`
- `policy`

This layer is useful for:
- debugging extraction quality
- surfacing structured snippets in the dashboard
- providing an additional retrieval/context path

It is not yet intended as a complete ontology or knowledge graph.

## Provider split (current)

Docstore now uses different providers for different tasks.

### OpenAI
Used for:
- embeddings only

Current default:
- `text-embedding-3-large`

### Groq
Used for:
- chunk question generation
- question rewrite
- chat answer generation

Current configured chat/question model family:
- `openai/gpt-oss-20b`

This split keeps embeddings stable while using a cheaper/faster generative path for retrieval-language generation and answers.

## Experimental / shelved work

### Docling
Docling is installed separately on the VPS and extractor selection support exists in code.

What we learned:
- Docling can be installed and invoked
- Docling improves structure in some cases
- Docling did not solve glyph corruption cleanly for the target handbook
- Docling runtime on the current VPS was too slow for regular use

Conclusion:
- keep Docling as an experimental alternate extractor backend
- do **not** use it as the normal production path on this VPS for now
- likely revisit on a GPU machine or faster host later

## Important Routes

### Web
- `/`
- `/signup/`
- `/login/`
- `/logout/`
- `/dashboard/`
- `/dashboard/documents/`
- `/dashboard/urls/`
- `/dashboard/chat/`
- `/dashboard/connectors/`
- `/dashboard/proxi-web/`
- `/dashboard/api-keys/`
- `/dashboard/staff/`
- `/documents/<id>/`
- `/documents/<id>/facts/`
- `/documents/<id>/chunks/`
- `/documents/<id>/search/`
- `/documents/<id>/download/`
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
- `InviteToken`

### documents
- `Document`
- `DocumentVersion`
- `Chunk`
- `ExtractedFact`

### ingestion
- `IngestionJob`

### connectors
- `Connector`
- `ConnectorSyncRun`
- `ExternalDocumentBinding`

## Environment Notes

### OpenAI embeddings
```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_EMBEDDING_MODEL=text-embedding-3-large
```

### Groq generation/chat
```env
GROQ_API_KEY=...
GROQ_BASE_URL=https://api.groq.com/openai/v1
DEFAULT_CHAT_MODEL=openai/gpt-oss-20b
QUESTION_GEN_MODEL=openai/gpt-oss-20b
```

### LLM question-generation guardrails
Current enrichment guardrails:

```env
QUESTION_GEN_MIN_CHARS=300
QUESTION_GEN_MAX_CHUNKS=40
```

Meaning:
- only chunks above a minimum size are eligible
- only a capped number of chunks per ingestion run use the LLM question-generation path
- noisy chunks still fall back to heuristic question generation

### Storage
Production currently uses MinIO-backed object storage.
User-facing download URLs are streamed through Django so raw internal MinIO URLs are not exposed.

### Celery
Docstore uses its own queue:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Worker should consume the `docstore` queue.

### Microsoft / SharePoint OAuth scaffold
Still foundation-level, not fully productized.
Expected env:

```env
MS_GRAPH_CLIENT_ID=...
MS_GRAPH_CLIENT_SECRET=...
MS_GRAPH_REDIRECT_URI=https://docstore.oddsmith.net/connect/microsoft/callback/
MS_GRAPH_TENANT_ID=common
MS_GRAPH_SCOPES=openid profile email offline_access Files.Read Sites.Read.All User.Read
```

## API keys

Dashboard users can create and revoke API keys from:
- `/dashboard/api-keys/`

Behavior:
- raw key shown once
- only prefix + hash stored
- revoke disables without deleting the DB record
- workspace-scoped and tenant-wide keys supported
- custom API-key guard handles tenant/workspace inference where possible

## Operational Notes
- production deploy path uses Pi → VPS rsync
- `.env` is intentionally excluded from deploy sync
- generated vectors live in Postgres, not SQLite
- current production-safe extraction path is the standard extractor
- retrieval quality still depends heavily on extraction quality for PDFs with glyph/encoding problems
- document-scoped search pages are now a first-class debugging tool and should be used heavily during tuning

## Related docs
- see `docs/workflows/retrieval-and-ingestion.md` for the current workflow and tuning notes

## Good Next Steps
- keep improving chunk-question quality and cost discipline
- improve exact-list ranking for near-miss chunks (e.g. “floating holidays” vs “paid holidays”)
- improve PDF cleanup / extraction quality further
- continue SharePoint productization
- add more retrieval evaluation fixtures / benchmark questions
