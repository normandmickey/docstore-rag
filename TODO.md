# TODO

## Dashboard / UX
- [ ] Make Documents page show file-uploaded documents only by default
- [ ] Add selective purge from Trash instead of only “purge all shown”
- [ ] Add deleted timestamp in Trash
- [ ] Add deleted-by tracking for soft delete actions
- [ ] Add recent activity cards/feed to Overview
- [ ] Improve empty states and copy polish across Overview, Documents, URLs, Chat, and Connectors pages
- [ ] Consider overview quick actions (Upload file, Ingest URLs, Ask question, Connect Microsoft)
- [ ] Consider document filters by source type, collection, and status

## Documents
- [ ] Add document detail page
- [ ] Add reingest action for latest document version
- [ ] Add version history expander / version detail view
- [ ] Show more explicit ingestion history per document
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

## Chat / retrieval
- [ ] Add `/api/v1/chat/` endpoint
- [ ] Improve answer citations/source formatting in dashboard chat
- [ ] Improve chunking strategy for long documents
- [ ] Add better snippet extraction for retrieved chunks
- [ ] Consider chat history per workspace
- [ ] Add document-only / collection-only / workspace-wide chat scopes

## Parsing / ingestion
- [ ] Add better DOCX handling for headings/tables/lists
- [ ] Consider OCR support for image-heavy PDFs later if needed
- [ ] Add richer HTML cleanup / readability extraction
- [ ] Add support for additional formats only as needed (e.g. CSV, XLSX, PPTX)

## Deletion lifecycle
- [ ] Add selective purge from Trash UI
- [ ] Add trash search/filtering
- [ ] Add restore/purge bulk summary messages with filenames or counts by type
- [ ] Consider retention policy for soft-deleted docs

## Connectors
- [ ] Add SharePoint site/drive/folder picker UI
- [ ] Link Connector records to per-user ExternalAccount records
- [ ] Use user-owned Microsoft tokens for Graph browsing/sync
- [ ] Add token refresh handling for Microsoft accounts
- [ ] Add “sync now” UI for connectors
- [ ] Add connector sync history page
- [ ] Add scheduled/incremental SharePoint sync
- [ ] Add better connector setup docs in-app

## API / platform
- [ ] Add API endpoints for connector management once UX is settled
- [ ] Add API auth/authorization hardening review
- [ ] Add server-side tests for upload/version/delete/restore/purge flows
- [ ] Add tests for URL ingest + duplicate handling
- [ ] Add tests for chat/retrieval flows

## Config / maintenance
- [ ] Clean up deprecated django-allauth settings warnings
- [ ] Document dashboard subpage structure in README
- [ ] Document delete/restore/purge API endpoints in README
- [ ] Document URL ingest API endpoint and crawl behavior in README
