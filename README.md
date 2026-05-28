# Docstore RAG

A multi-tenant document storage and embedding service for RAG, built with Django for admin visibility and operational control.

## Goals

- Multi-tenant document storage
- Workspace/collection isolation
- Async ingestion pipeline
- Chunking + embeddings
- Postgres + PGVector retrieval
- S3/MinIO-compatible blob storage
- Django admin for documents, jobs, tenants, and failures
- API-first design for app integrations

## Planned Stack

- Django
- Django REST Framework
- Postgres
- PGVector
- Celery + Redis
- MinIO/S3-compatible object storage
- OpenAI embeddings by default
- Local OpenAI-compatible LLM optional for answer generation

## Core Concepts

- **Tenant**: top-level account/org boundary
- **Workspace**: logical knowledge base inside a tenant
- **Collection**: optional namespace/tag within a workspace
- **Document**: uploaded source file and metadata
- **Chunk**: retrievable text unit with embedding
- **Ingestion Job**: async parsing/chunking/embedding job

## Proposed App Layout

- `control` — tenants, workspaces, API keys, admin controls
- `documents` — document records, versions, source metadata, storage references
- `ingestion` — pipelines, parsers, chunking, jobs, worker tasks
- `retrieval` — vector search, filters, citations, answer assembly
- `providers` — embedding/generation/storage adapters
- `audit` — query logs, retrieval logs, usage events

## V1 Priorities

1. Tenant/workspace isolation
2. Upload file -> queue ingestion -> parse -> chunk -> embed -> searchable
3. Search endpoint with citations
4. Admin visibility into failures and document/job state
5. Delete/reindex flows

## Deliberate Non-Goals for V1

- Full multimodal document understanding
- Advanced OCR/layout grounding by default
- Huge connector marketplace
- Fancy end-user frontend
- Agent workflows beyond basic query/search APIs

## Why Django

Django gives us:
- mature admin for tenant/document/job operations
- fast model iteration
- strong ORM fit for Postgres-heavy systems
- good internal tooling without building a separate ops panel first

## Suggested Data Model

### control_tenant
- id
- name
- slug
- status
- metadata_json
- created_at
- updated_at

### control_workspace
- id
- tenant_id
- name
- slug
- default_embedding_model
- default_chunk_size
- metadata_json
- created_at
- updated_at

### documents_document
- id
- tenant_id
- workspace_id
- collection
- status
- filename
- mime_type
- size_bytes
- object_key
- content_hash
- source_type
- source_url
- uploaded_by
- created_at
- updated_at

### documents_documentversion
- id
- document_id
- version_number
- object_key
- content_hash
- parse_status
- extraction_metadata_json
- created_at

### documents_chunk
- id
- tenant_id
- workspace_id
- document_id
- document_version_id
- chunk_index
- text
- token_count
- metadata_json
- embedding vector
- created_at

### ingestion_ingestionjob
- id
- tenant_id
- workspace_id
- document_id
- document_version_id
- status
- stage
- error_text
- started_at
- finished_at
- created_at

### control_apikey
- id
- tenant_id
- workspace_id nullable
- label
- key_prefix
- key_hash
- scopes_json
- last_used_at
- active
- created_at

## Retrieval API V1

### POST `/api/v1/documents/`
Create document + upload metadata, then queue ingestion.

### POST `/api/v1/documents/{id}/ingest/`
Force ingestion or reingestion.

### POST `/api/v1/search/`
Inputs:
- query
- workspace
- collection optional
- top_k
- metadata filters

Returns:
- chunk matches
- scores
- document metadata
- citations

### POST `/api/v1/query/`
Inputs:
- query
- workspace
- retrieval settings
- generation toggle/model

Returns:
- answer
- citations
- supporting chunks

## Operational Notes

- Use shared tables with explicit `tenant_id` + `workspace_id` in V1.
- Consider Postgres RLS later if needed.
- Keep embeddings provider-abstracted.
- Keep original files out of Postgres; use object storage.
- Keep answer generation separate from retrieval internals so retrieval can be debugged directly.

## Recommended V1 Defaults

- Postgres + PGVector only
- OpenAI embeddings first
- local OpenAI-compatible generation optional
- MinIO in local/dev, S3/R2 in production
- Celery workers for parsing/embedding jobs

## Next Steps

1. Scaffold Django project + apps
2. Add docker-compose for Postgres/Redis/MinIO
3. Implement initial models + admin
4. Add upload + ingestion job flow
5. Add chunk + embedding pipeline
6. Add search endpoint
