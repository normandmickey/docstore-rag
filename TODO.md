# TODO

## Chatbots / multi-platform bot runner
- [ ] Add `chatbots` app as a tenant-scoped control plane for Telegram, Discord, and Zoom-style bots
- [ ] Keep bot hosting outside Django core in a separate `docstore-bot-runner` service/plugin layer
- [ ] Add core models: `ChatbotIntegration`, `ChatbotEndpoint`, `ChatbotDefinition`, `ChatbotEndpointBinding`, `ChatbotBuild`, `ChatbotDeployment`, `ChatbotConversation`, `ChatbotMessage`, `ChatbotEventLog`
- [ ] Add admin visibility for chatbot integrations, endpoint mappings, builds, deployments, conversations, messages, and event logs
- [ ] Add dashboard pages for chatbot integrations, definitions, endpoint mappings, deployments, conversations, and logs
- [ ] Add runner-facing APIs for endpoint resolution, message/event ingest, build manifest fetch, and runner heartbeat
- [ ] Start with generated manifest/config artifacts rather than arbitrary bespoke generated code per tenant
- [ ] Add Telegram as the first live runtime target
- [ ] Add Discord after Telegram routing/logging is stable
- [ ] Split Zoom Team Chat and Zoom Meeting Assistant into distinct integration types if/when Zoom ships
- [ ] Add deployment/build status visibility in dashboard so tenants/admins can see whether a bot is configured, built, and running
- [ ] Add logging policy controls for message retention, raw payload retention, and operational event verbosity

## Dashboard / UX
- [ ] Make Documents page show file-uploaded documents only by default
- [ ] Add selective purge from Trash instead of only “purge all shown”
- [ ] Add deleted timestamp in Trash
- [ ] Add deleted-by tracking for soft delete actions
- [ ] Add recent activity cards/feed to Overview
- [ ] Improve empty states and copy polish across Overview, Documents, URLs, Chat, Connectors, and API Keys pages
- [ ] Consider overview quick actions (Upload file, Ingest URLs, Ask question, Connect Microsoft, Create API key)
- [ ] Consider document filters by source type, collection, status, and date
- [ ] Show recent successful/failed ingestion activity on Overview
- [ ] Consider a lightweight in-app changelog / “What’s new” section

## Documents
- [ ] Add document detail page
- [ ] Add reingest action for latest document version
- [ ] Add version history expander / version detail view
- [ ] Show more explicit ingestion history per document
- [ ] Add document metadata panel (source type, source URL, file size, mime type, content hash)
- [ ] Add collection management / collection filters in the Documents page
- [ ] Consider restore/purge API responses in dashboard without full page reloads

## URL ingestion
- [ ] Tighten URL-specific versioning by normalized source URL + changed content
- [ ] Add crawl summary/history view
- [ ] Add domain include/exclude controls for crawl mode
- [ ] Add canonical URL handling improvements
- [ ] Improve readable/article extraction quality further
- [ ] Consider robots/sitemap-aware crawling rules
- [ ] Add URL ingestion result details in UI (created/versioned/skipped/failed rows)
- [ ] Consider per-run URL ingest logs for debugging
- [ ] Add URL-specific delete/purge affordances from the URLs page
- [ ] Show URL import timestamps / last fetched timestamps
- [ ] Consider re-fetch / refresh flow for URL documents

## Chat / retrieval
- [ ] Improve answer citations/source formatting in dashboard chat
- [ ] Improve chunking strategy for long documents
- [ ] Add better snippet extraction for retrieved chunks
- [ ] Consider chat history per workspace
- [ ] Add document-only / collection-only / workspace-wide chat scopes
- [ ] Add follow-up question UX in the dashboard chat page
- [ ] Consider streaming responses for long answers
- [ ] Add clearer “no answer found” / “insufficient context” behavior in API + UI

## Parsing / ingestion
- [ ] Add better DOCX handling for headings/tables/lists
- [ ] Add OCR fallback support for scanned/image-heavy PDFs
- [ ] If extracted text is empty, do not mark the document/version as ready; surface a clear no-text-extracted failure state instead
- [ ] Add richer HTML cleanup / readability extraction
- [ ] Add support for additional formats only as needed (e.g. CSV, XLSX, PPTX)
- [ ] Add ingestion metrics/logging for chunk counts, timing, and embedding failures
- [ ] Add parse failure categorization (network, parser, embeddings, storage)
- [ ] Evaluate ColPali / hybrid vision retrieval for layout-heavy PDFs and scanned documents
  - [ ] render PDF pages to images for optional page-level vision retrieval
  - [ ] keep text retrieval as the default path for normal documents
  - [ ] use OCR fallback and/or vision retrieval when text extraction is empty or poor
  - [ ] decide whether ColPali should run locally, on a separate service, or via another inference path
  - [ ] design page-level/page-patch embedding storage and retrieval flow

## Deletion lifecycle
- [ ] Add selective purge from Trash UI
- [ ] Add trash search/filtering
- [ ] Add restore/purge bulk summary messages with filenames or counts by type
- [ ] Consider retention policy for soft-deleted docs
- [ ] Add deleted timestamp and deleted-by persistence in the model layer
- [ ] Consider delayed purge / scheduled cleanup job

## API keys / API platform
- [ ] Add example snippets directly on the API Keys page for search/chat/url-ingest/delete flows
- [ ] Add explicit copy examples for workspace-scoped vs tenant-wide keys
- [ ] Add API key rename/edit labels flow
- [ ] Add revoke-all / bulk revoke UX
- [ ] Add audit trail for API key creation/revoke/use
- [ ] Add API key rate limiting / abuse controls
- [ ] Add API auth/authorization hardening review
- [ ] Add API error response docs and examples
- [ ] Consider API versioning strategy before the surface area grows further
- [ ] Add JSON schema or OpenAPI generation for the public API

## Connectors
- [ ] Add ElevenLabs connector for voice workflows (voice selection, TTS generation, and possible audio response/export hooks)
- [ ] Add SharePoint site/drive/folder picker UI
- [ ] Link Connector records to per-user ExternalAccount records
- [ ] Use user-owned Microsoft tokens for Graph browsing/sync
- [ ] Add token refresh handling for Microsoft accounts
- [ ] Add “sync now” UI for connectors
- [ ] Add connector sync history page
- [ ] Add scheduled/incremental SharePoint sync
- [ ] Add better connector setup docs in-app
- [ ] Add disconnect / reconnect Microsoft account flows
- [ ] Add external account health/status indicators (token expired, permissions missing, etc.)
- [ ] Add Confluence connector support (space/page sync, page metadata, updated-page re-sync)
- [ ] Add Jira connector support (project/JQL sync, issue + comment ingestion, operational knowledge model)
- [ ] Consider a broader Atlassian connector layer/shared auth if both Confluence and Jira ship
- [ ] Consider connector support for Google Drive / Dropbox later only if needed

## Security / permissions
- [ ] Add tenant Members management page for owner/admin roles (list members, invite users, change roles, remove memberships)
- [ ] Start with tenant-wide membership roles only (owner/admin/member); add workspace-specific ACLs later only if truly needed
- [ ] Encrypt or otherwise better-protect stored refresh tokens and external account secrets at rest
- [ ] Review tenant/workspace ownership and permission checks across dashboard actions
- [ ] Add explicit authorization tests for cross-tenant / cross-workspace access attempts
- [ ] Consider CSRF / session hardening review for dashboard POST actions
- [ ] Review exposure of IDs in the UI and keep end-user-facing APIs tenant-opaque where possible

## Testing / reliability
- [ ] Add server-side tests for upload/version/delete/restore/purge flows
- [ ] Add tests for URL ingest + duplicate handling
- [ ] Add tests for chat/retrieval flows
- [ ] Add tests for API key auth (workspace-scoped, tenant-wide, revoked, bad key)
- [ ] Add tests for SharePoint OAuth/account connection flow once stabilized
- [ ] Add smoke-test script for post-deploy verification on VPS

## README / docs / maintenance
- [ ] Document dashboard subpage structure in README
- [ ] Document the new API-key inferred tenant/workspace behavior more explicitly in README
- [ ] Add sample request/response bodies for document upload endpoint in README
- [ ] Add examples for tenant-wide API keys in README
- [ ] Clean up deprecated django-allauth settings warnings
- [ ] Add future MinIO/S3 migration checklist:
  - [ ] audit code for filesystem-only assumptions (`.path`, direct `open()`, raw absolute paths)
  - [ ] keep storage backend fully env-switchable
  - [ ] stand up MinIO bucket with stable object key layout matching current `Document.file` names
  - [ ] sync existing local media files into object storage without changing DB file keys
  - [ ] verify upload/read/ingest/delete/restore/purge flows against object storage
  - [ ] document rollback path back to local filesystem storage
- [ ] Keep TODO.md trimmed as items ship so it stays credible
