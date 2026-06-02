# Docstore RAG

A multi-tenant document storage, retrieval, chat, and control-plane service for document-grounded workflows, built with Django for admin visibility and operational control.

## Live
- App: `https://docstore.oddsmith.net`

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
- tenant-scoped support flows (SMS/voice scaffolding)
- optional voice transcript ingest endpoint
- chatbot control plane for Telegram/Discord-style integrations

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

### Support + voice integration
- tenant-scoped support settings and channel scaffolding
- Twilio SMS/voice webhook support in Django
- optional `VoiceCallRecord` storage via:
  - `POST /api/v1/integrations/voice/calls/ingest/`
- admin visibility for `VoiceCallRecord`
- dashboard visibility for support voice calls:
  - `/dashboard/support/calls/`
- legacy voicemail-style support threads hidden from main support inbox

### Chatbot control plane
Docstore now includes a tenant-scoped chatbot control plane for external bot runtimes.

Current pieces live in Django:
- `ChatbotIntegration`
- `ChatbotEndpoint`
- `ChatbotDefinition`
- `ChatbotEndpointBinding`
- `ChatbotBuild`
- `ChatbotDeployment`
- `ChatbotConversation`
- `ChatbotMessage`
- `ChatbotEventLog`

Dashboard pages now include:
- `/dashboard/chatbots/`
- create/edit integration forms
- create definition form
- create endpoint form
- create binding form
- definition detail page

Runner-facing APIs now include:
- `POST /api/v1/chatbots/resolve/`
- `POST /api/v1/chatbots/messages/ingest/`
- `POST /api/v1/chatbots/events/ingest/`

Current live bot runtimes using this control plane:
- Telegram via `docstore-bot-runner`
- Discord via `docstore-bot-runner`

## Architecture

### Core concepts
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

### App layout
- `control` — auth flow, tenants, workspaces, API keys, external accounts, dashboard pages
- `documents` — documents, versions, chunks, facts, upload handling, duplicate/version logic
- `ingestion` — parsing, chunking, question generation, embeddings, Celery jobs
- `retrieval` — chunk retrieval, answer assembly, dashboard chat/search
- `audit` — retrieval logging
- `connectors` — SharePoint connector models, Graph helper, sync runs, bindings
- `support` — tenant-scoped support channels, conversations, Twilio flows
- `integrations.voice` — optional voice transcript ingest model/view/admin
- `chatbots` — chatbot integrations, definitions, logs, dashboard control-plane pages

### Bot/runtime boundary
Docstore is the **control plane**, not the long-running bot runtime.

Docstore owns:
- tenant/workspace config
- chatbot integrations + definitions
- resolve/logging APIs
- retrieval/chat APIs
- dashboard/admin visibility

External runtimes own:
- platform-specific webhooks/gateway connections
- message/session handling
- retries and transport behavior
- execution-plane behavior

Current runtime repos/services:
- `docstore-bot-runner` — Telegram + Discord
- `docstore-voice-agent` — realtime Twilio voice agent

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

## Provider split (current)

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

## Install / Bootstrap

For a fresh-server install guide, see:

- `INSTALL.md`
- `scripts/bootstrap-docstore-server.sh`

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
- `/dashboard/support/`
- `/dashboard/support/calls/`
- `/dashboard/chatbots/`
- `/documents/<id>/`
- `/documents/<id>/facts/`
- `/documents/<id>/chunks/`
- `/documents/<id>/search/`
- `/documents/<id>/download/`
- `/healthz/`
- `/connect/microsoft/`
- `/connect/microsoft/callback/`

### API
- `GET /api/schema/`
- `GET /api/docs/`
- `POST /api/v1/documents/`
- `POST /api/v1/documents/delete/`
- `POST /api/v1/documents/restore/`
- `POST /api/v1/documents/purge/`
- `POST /api/v1/urls/ingest/`
- `POST /api/v1/search/`
- `POST /api/v1/chat/`
- `POST /api/v1/support/channel-lookup/`
- `POST /api/v1/support/shipping/health/`
- `POST /api/v1/support/shipping/search/`
- `POST /api/v1/support/shipping/package/`
- `POST /api/v1/support/shipping/latest-status/`
- `POST /api/v1/integrations/voice/calls/ingest/`
- `POST /api/v1/chatbots/resolve/`
- `POST /api/v1/chatbots/messages/ingest/`
- `POST /api/v1/chatbots/events/ingest/`

### API docs
- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`

### Multi-workspace ingest
Docstore now supports assigning one ingested document to multiple workspaces without duplicating the file, versions, chunks, or embeddings.

#### File/document ingest example
```json
{
  "tenant_id": 2,
  "workspace_id": 3,
  "additional_workspace_ids": [4, 5],
  "collection": "hr"
}
```

#### URL ingest example
```json
{
  "tenant_id": 2,
  "workspace_id": 3,
  "additional_workspace_ids": [4, 5],
  "urls": ["https://example.com/handbook"],
  "crawl_mode": "single"
}
```

The response now includes `assigned_workspace_ids` so callers can verify which workspaces the document was assigned to at ingest time.

### Language examples

#### Python
```python
import requests

BASE_URL = "https://docstore.oddsmith.net"
API_KEY = "YOUR_DOCSTORE_API_KEY"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
}

chat_payload = {
    "tenant_id": 2,
    "workspace_id": 3,
    "question": "What is the PTO policy?",
    "top_k": 5,
}
chat_response = requests.post(f"{BASE_URL}/api/v1/chat/", json=chat_payload, headers=HEADERS, timeout=60)
chat_response.raise_for_status()
print(chat_response.json())

with open("employee-handbook.pdf", "rb") as fh:
    upload_response = requests.post(
        f"{BASE_URL}/api/v1/documents/",
        data={
            "tenant_id": 2,
            "workspace_id": 3,
            "additional_workspace_ids": [4, 5],
            "collection": "hr",
        },
        files={"file": ("employee-handbook.pdf", fh, "application/pdf")},
        headers=HEADERS,
        timeout=120,
    )
upload_response.raise_for_status()
print(upload_response.json())
```

#### Node.js
```js
const fs = require('fs');
const FormData = require('form-data');

const BASE_URL = 'https://docstore.oddsmith.net';
const API_KEY = 'YOUR_DOCSTORE_API_KEY';
const headers = {
  Authorization: `Bearer ${API_KEY}`,
};

async function run() {
  const chatResponse = await fetch(`${BASE_URL}/api/v1/chat/`, {
    method: 'POST',
    headers: {
      ...headers,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      tenant_id: 2,
      workspace_id: 3,
      question: 'What is the PTO policy?',
      top_k: 5,
    }),
  });
  console.log(await chatResponse.json());

  const form = new FormData();
  form.append('tenant_id', '2');
  form.append('workspace_id', '3');
  form.append('additional_workspace_ids', '4');
  form.append('additional_workspace_ids', '5');
  form.append('collection', 'hr');
  form.append('file', fs.createReadStream('employee-handbook.pdf'));

  const uploadResponse = await fetch(`${BASE_URL}/api/v1/documents/`, {
    method: 'POST',
    headers: {
      ...headers,
      ...form.getHeaders(),
    },
    body: form,
  });
  console.log(await uploadResponse.json());
}

run().catch(console.error);
```

#### .NET (C#)
```csharp
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

var baseUrl = "https://docstore.oddsmith.net";
var apiKey = "YOUR_DOCSTORE_API_KEY";
using var client = new HttpClient();
client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);

var chatPayload = new
{
    tenant_id = 2,
    workspace_id = 3,
    question = "What is the PTO policy?",
    top_k = 5
};
var chatJson = JsonSerializer.Serialize(chatPayload);
var chatResponse = await client.PostAsync(
    $"{baseUrl}/api/v1/chat/",
    new StringContent(chatJson, Encoding.UTF8, "application/json")
);
chatResponse.EnsureSuccessStatusCode();
Console.WriteLine(await chatResponse.Content.ReadAsStringAsync());

using var form = new MultipartFormDataContent();
form.Add(new StringContent("2"), "tenant_id");
form.Add(new StringContent("3"), "workspace_id");
form.Add(new StringContent("4"), "additional_workspace_ids");
form.Add(new StringContent("5"), "additional_workspace_ids");
form.Add(new StringContent("hr"), "collection");
form.Add(new StreamContent(File.OpenRead("employee-handbook.pdf")), "file", "employee-handbook.pdf");

var uploadResponse = await client.PostAsync($"{baseUrl}/api/v1/documents/", form);
uploadResponse.EnsureSuccessStatusCode();
Console.WriteLine(await uploadResponse.Content.ReadAsStringAsync());
```

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
```env
QUESTION_GEN_MIN_CHARS=300
QUESTION_GEN_MAX_CHUNKS=40
```

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

### Voice integration toggle
Optional voice transcript ingest uses:
```env
VOICE_INTEGRATION_ENABLED=true
```

### Microsoft / SharePoint OAuth scaffold
```env
MS_GRAPH_CLIENT_ID=...
MS_GRAPH_CLIENT_SECRET=...
MS_GRAPH_REDIRECT_URI=https://docstore.oddsmith.net/connect/microsoft/callback/
MS_GRAPH_TENANT_ID=common
MS_GRAPH_SCOPES=openid profile email offline_access Files.Read Sites.Read.All User.Read
```

### Google Drive OAuth setup
The Google Drive connector now supports:
- Google account linking
- recent-file browse/search
- one-off file import
- folder-backed connector setup
- basic sync-now flow
- lightweight folder browser UI
- recursive folder sync for connector-backed imports

To enable it in production:

1. In Google Cloud, enable the **Google Drive API**.
2. Configure the OAuth consent screen.
   - If the app is still in testing, add your Google account as a test user.
3. Create an **OAuth client ID** of type **Web application**.
4. Add this authorized redirect URI exactly:
   - `https://docstore.oddsmith.net/connect/google/callback/`
5. Put these values in the Docstore `.env` on the VPS checkout:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://docstore.oddsmith.net/connect/google/callback/
GOOGLE_SCOPES=openid email profile https://www.googleapis.com/auth/drive.readonly
```

Current env location on the VPS:
- `/home/norm/sites/docstore_checkout/.env`

After updating `.env`, rerun the deploy/reload path:

```bash
/home/norm/bin/deploy-docstore
```

Then test from:
- `/dashboard/connectors/`

Common Google OAuth gotchas:
- `redirect_uri_mismatch` means the Google OAuth client redirect URI does not exactly match the configured callback URL.
- If the app is still in testing, accounts not added as test users may be blocked.

### Zoom Chat OAuth setup
For Zoom Chat outbound replies, Docstore now has a minimal OAuth/install callback flow that can store install-derived credentials back into a Zoom Chat chatbot integration.

Required env:

```env
ZOOM_CLIENT_ID=...
ZOOM_CLIENT_SECRET=...
ZOOM_REDIRECT_URI=https://docstore.oddsmith.net/dashboard/chatbots/integrations/zoom/callback/
```

Current behavior:
- create a `Zoom Chat` chatbot integration in the dashboard
- store Zoom app/client id in `external_app_id`
- use the dashboard connect flow to authorize/install the Zoom app
- callback stores `access_token` and, when available, `bot_jid` in `credentials_json`

This is the missing bridge between Zoom webhook validation and actual outbound Zoom Chat reply delivery.

### Shipping manager integration
Docstore can now call a separate internal shipping manager service instead of querying carrier APIs directly.

Required env:

```env
SHIPPING_MANAGER_BASE_URL=https://ship.oddsmith.net
SHIPPING_MANAGER_API_KEY=...
```

Current API bridge endpoints in Docstore:
- `POST /api/v1/support/shipping/health/`
- `POST /api/v1/support/shipping/search/`
- `POST /api/v1/support/shipping/package/`
- `POST /api/v1/support/shipping/latest-status/`

These routes are intended for trusted signed-in tenant admins/owners or Bearer API-key callers already scoped to the tenant/workspace.

### AgentMail setup
Docstore can now use an AgentMail inbox for project email.

Current minimal env support:

```env
AGENTMAIL_API_KEY=...
AGENTMAIL_INBOX_ID=docstore@agentmail.to
AGENTMAIL_BASE_URL=https://api.agentmail.to/v0
```

Current code support includes:
- a lightweight AgentMail client wrapper at `control/agentmail.py`
- a test send command:

```bash
.venv/bin/python manage.py send_agentmail_test you@example.com
```

This is intended as the safe first step before wiring AgentMail into user-facing invite/support workflows.

Current live app wiring now includes:
- invite emails when staff create an invite with an email address
- password reset emails routed through the custom allauth account adapter
- support acknowledgement emails for newly created inbound support conversations when the support contact has an email stored in metadata

These mail hooks are intentionally non-fatal: if AgentMail send fails, the underlying invite/support flow still succeeds.

## API keys
Dashboard users can create and revoke API keys from:
- `/dashboard/api-keys/`

Behavior:
- raw key shown once
- only prefix + hash stored
- revoke disables without deleting the DB record
- workspace-scoped and tenant-wide keys supported
- chatbot/voice runtimes rely on these API keys for resolve/log/chat ingest flows

## Operational Notes
- current production deploy path is git-based Pi → VPS deploy helper
- `.env` is intentionally excluded from deploy sync
- generated vectors live in Postgres, not SQLite
- current production-safe extraction path is the standard extractor
- chatbot + voice runtimes are separate services and should not be folded into Django
- document-scoped search pages remain a first-class debugging tool during tuning

## Reporting
Docstore now has an initial `reports` app scaffold with a first support activity report:
- route: `/dashboard/reports/support/`
- filters: start date / end date
- exports: XLSX

The current pattern is intentionally simple:
- native Django views for report pages
- `openpyxl` for spreadsheet export
- room to add PDF exports later

## Related docs
- `DEPLOY.md`
- `docs/chatbots-architecture.md`

## Good Next Steps
- keep improving chunk-question quality and cost discipline
- improve exact-list ranking for near-miss chunks
- continue SharePoint productization
- add more retrieval evaluation fixtures / benchmark questions
- continue chatbot UX polish and richer endpoint binding flows
- continue voice-agent quality and transcript sync refinement
