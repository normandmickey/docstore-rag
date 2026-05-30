# Chatbots Architecture

## Goal
Build tenant-owned, workspace-aware chatbot integrations for platforms such as Telegram, Discord, and Zoom while keeping docstore-rag as the control plane and a separate bot runner as the execution plane.

## Core design
- **Docstore core** owns tenant/workspace config, bot definitions, generated manifests, deployment records, conversations, messages, and logs.
- **Bot runner services/plugins** own platform-specific runtime behavior such as webhook handling, sockets, retries, and outbound sends.
- **Workspace** provides default grounding context.
- **Tenant** owns integrations, credentials, permissions, and logs.

## Hosting boundary
- Keep bot hosting **outside Django core**.
- Add a dedicated runtime service such as `docstore-bot-runner`.
- Treat generated bot artifacts as manifest/config-first, template-driven code second, and arbitrary bespoke code last.

## Recommended model graph

### ChatbotIntegration
Tenant-owned installed integration or app.

Fields:
- tenant
- platform (`telegram`, `discord`, `zoom_chat`, `zoom_meeting`)
- name
- status (`draft`, `active`, `error`, `disabled`)
- active
- external_app_id
- external_bot_id
- webhook_url
- webhook_status
- credentials_json (v1; later secret refs)
- metadata_json
- created_at
- updated_at

### ChatbotEndpoint
A routed platform surface within an integration.

Fields:
- integration
- tenant
- endpoint_type (`dm`, `group`, `channel`, `thread`, `meeting`, `chat_room`)
- external_id
- external_parent_id
- display_name
- default_workspace
- mode (`dm_only`, `mention_only`, `always_on`, `meeting_assistant`)
- active
- metadata_json
- created_at
- updated_at

### ChatbotDefinition
The bot behavior layer.

Fields:
- tenant
- integration
- name
- slug
- default_workspace
- persona_prompt
- system_prompt
- runtime_mode (`shared_runner`, `isolated_runner`)
- template_name
- template_version
- allowed_tools_json
- response_policy_json
- handoff_policy_json
- logging_policy_json
- active
- metadata_json
- created_at
- updated_at

### ChatbotEndpointBinding
Maps endpoints to bot definitions with optional workspace override.

Fields:
- bot_definition
- endpoint
- workspace_override
- active
- metadata_json
- created_at
- updated_at

### ChatbotBuild
Versioned generated artifact record.

Fields:
- bot_definition
- version
- status (`queued`, `building`, `ready`, `failed`, `deployed`)
- artifact_type (`config`, `template_bundle`)
- artifact_path
- generated_manifest_json
- build_log
- created_by
- created_at
- updated_at

### ChatbotDeployment
Tracks which build is active on which runner target.

Fields:
- bot_definition
- build
- runner_type
- runner_target
- status
- last_heartbeat_at
- last_error
- metadata_json
- created_at
- updated_at

### ChatbotConversation
Normalized conversation/thread container.

Fields:
- tenant
- workspace
- integration
- endpoint
- bot_definition
- platform
- external_conversation_id
- external_thread_id
- title
- status
- last_message_at
- metadata_json
- created_at
- updated_at

### ChatbotMessage
Normalized message log.

Fields:
- conversation
- direction (`inbound`, `outbound`, `system`)
- external_message_id
- sender_external_id
- sender_label
- body
- normalized_content_json
- retrieval_metadata_json
- model_metadata_json
- delivery_status
- created_at

### ChatbotEventLog
Operational logs for debugging and delivery visibility.

Fields:
- tenant
- integration
- endpoint
- bot_definition
- severity (`info`, `warning`, `error`)
- event_type
- message
- payload_json
- dedupe_key
- created_at

## API surface to add

### Dashboard/control APIs
- `POST /api/v1/chatbots/integrations/`
- `POST /api/v1/chatbots/definitions/`
- `POST /api/v1/chatbots/builds/`
- `POST /api/v1/chatbots/deployments/`
- `GET /api/v1/chatbots/conversations/`
- `GET /api/v1/chatbots/logs/`

### Runner APIs
- `POST /api/v1/chatbots/resolve/`
- `POST /api/v1/chatbots/events/ingest/`
- `POST /api/v1/chatbots/messages/ingest/`
- `GET /api/v1/chatbots/builds/<id>/manifest/`
- `POST /api/v1/chatbots/runners/heartbeat/`

## Logging guidance
Always store:
- inbound/outbound message text
- sender/chat identifiers
- tenant/workspace resolution
- bot definition used
- retrieval/model summaries
- event failures and retries

Do not default to storing full raw platform payloads everywhere. Put raw payload retention behind a flag.

## Recommended rollout order
1. Telegram
2. Discord
3. Zoom chat
4. Zoom meeting assistant

## Recommended runtime shape
Start with a single shared runner service:
- `docstore-bot-runner`

Then split by platform only if operationally needed.
