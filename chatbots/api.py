from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from control.api_auth import get_api_key_from_header
from control.api_guard import resolve_request_context

from .models import ChatbotConversation, ChatbotDefinition, ChatbotEndpoint, ChatbotEventLog, ChatbotIntegration, ChatbotMessage


class ChatbotResolveSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=ChatbotIntegration.PLATFORM_CHOICES)
    integration_id = serializers.IntegerField(required=False)
    runner_key = serializers.CharField(required=False, allow_blank=True)
    external_bot_id = serializers.CharField(required=False, allow_blank=True)
    external_app_id = serializers.CharField(required=False, allow_blank=True)
    external_id = serializers.CharField(required=False, allow_blank=True)
    endpoint_type = serializers.CharField(required=False, allow_blank=True)


class ChatbotEventIngestSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    integration_id = serializers.IntegerField(required=False)
    endpoint_id = serializers.IntegerField(required=False)
    bot_definition_id = serializers.IntegerField(required=False)
    severity = serializers.ChoiceField(choices=ChatbotEventLog.SEVERITY_CHOICES, required=False, default=ChatbotEventLog.SEVERITY_INFO)
    event_type = serializers.CharField()
    message = serializers.CharField(required=False, allow_blank=True)
    payload_json = serializers.JSONField(required=False)
    dedupe_key = serializers.CharField(required=False, allow_blank=True)


class ChatbotMessageIngestSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    integration_id = serializers.IntegerField()
    endpoint_id = serializers.IntegerField(required=False)
    bot_definition_id = serializers.IntegerField(required=False)
    platform = serializers.ChoiceField(choices=ChatbotIntegration.PLATFORM_CHOICES)
    external_conversation_id = serializers.CharField(required=False, allow_blank=True)
    external_thread_id = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(required=False, allow_blank=True)
    direction = serializers.ChoiceField(choices=ChatbotMessage.DIR_CHOICES)
    external_message_id = serializers.CharField(required=False, allow_blank=True)
    sender_external_id = serializers.CharField(required=False, allow_blank=True)
    sender_label = serializers.CharField(required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)
    normalized_content_json = serializers.JSONField(required=False)
    retrieval_metadata_json = serializers.JSONField(required=False)
    model_metadata_json = serializers.JSONField(required=False)
    delivery_status = serializers.CharField(required=False, allow_blank=True)


class ChatbotResolveView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        api_key = get_api_key_from_header(request)
        if api_key is None:
            return Response({'detail': 'Authentication required.'}, status=401)

        serializer = ChatbotResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        integrations = ChatbotIntegration.objects.filter(
            tenant=api_key.tenant,
            platform=data['platform'],
            active=True,
        )
        integration_id = data.get('integration_id')
        if integration_id:
            integrations = integrations.filter(id=integration_id)
        runner_key = (data.get('runner_key') or '').strip()
        if runner_key:
            integrations = integrations.filter(runner_key=runner_key)
        external_bot_id = (data.get('external_bot_id') or '').strip()
        if external_bot_id:
            integrations = integrations.filter(external_bot_id=external_bot_id)
        external_app_id = (data.get('external_app_id') or '').strip()
        if external_app_id:
            integrations = integrations.filter(external_app_id=external_app_id)
        integration = integrations.first()
        if integration is None:
            return Response({'detail': 'Integration not found.'}, status=404)

        endpoint = None
        external_id = (data.get('external_id') or '').strip()
        if external_id:
            endpoint_qs = ChatbotEndpoint.objects.select_related('default_workspace').filter(
                integration=integration,
                external_id=external_id,
                active=True,
            )
            endpoint_type = (data.get('endpoint_type') or '').strip()
            if endpoint_type:
                endpoint_qs = endpoint_qs.filter(endpoint_type=endpoint_type)
            endpoint = endpoint_qs.first()

        binding = None
        bot_definition = None
        workspace = None
        if endpoint is not None:
            binding = endpoint.bot_bindings.select_related('bot_definition', 'workspace_override').filter(active=True).first()
            if binding is not None:
                bot_definition = binding.bot_definition
                workspace = binding.workspace_override or endpoint.default_workspace or bot_definition.default_workspace
        if bot_definition is None:
            bot_definition = integration.definitions.select_related('default_workspace').filter(active=True).order_by('name').first()
            if bot_definition is not None:
                workspace = workspace or bot_definition.default_workspace

        return Response({
            'tenant': {
                'id': integration.tenant_id,
                'name': integration.tenant.name,
                'slug': integration.tenant.slug,
            },
            'integration': {
                'id': integration.id,
                'name': integration.name,
                'platform': integration.platform,
                'status': integration.status,
                'runner_key': integration.runner_key,
                'external_app_id': integration.external_app_id,
                'external_bot_id': integration.external_bot_id,
                'webhook_url': integration.webhook_url,
                'webhook_status': integration.webhook_status,
                'credentials_json': integration.credentials_json,
                'metadata_json': integration.metadata_json,
            },
            'endpoint': {
                'id': endpoint.id if endpoint else None,
                'display_name': endpoint.display_name if endpoint else None,
                'external_id': endpoint.external_id if endpoint else None,
                'endpoint_type': endpoint.endpoint_type if endpoint else None,
                'mode': endpoint.mode if endpoint else None,
            },
            'bot_definition': {
                'id': bot_definition.id if bot_definition else None,
                'name': bot_definition.name if bot_definition else None,
                'slug': bot_definition.slug if bot_definition else None,
                'runtime_mode': bot_definition.runtime_mode if bot_definition else None,
                'template_name': bot_definition.template_name if bot_definition else None,
                'template_version': bot_definition.template_version if bot_definition else None,
                'persona_prompt': bot_definition.persona_prompt if bot_definition else '',
                'system_prompt': bot_definition.system_prompt if bot_definition else '',
                'allowed_tools_json': bot_definition.allowed_tools_json if bot_definition else {},
                'response_policy_json': bot_definition.response_policy_json if bot_definition else {},
                'handoff_policy_json': bot_definition.handoff_policy_json if bot_definition else {},
                'logging_policy_json': bot_definition.logging_policy_json if bot_definition else {},
            },
            'workspace': {
                'id': workspace.id if workspace else None,
                'name': workspace.name if workspace else None,
                'slug': workspace.slug if workspace else None,
            },
            'binding': {
                'id': binding.id if binding else None,
                'workspace_override_id': binding.workspace_override_id if binding else None,
            },
        })


class ChatbotEventIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChatbotEventIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, _workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )

        integration = ChatbotIntegration.objects.filter(id=data.get('integration_id'), tenant=tenant).first() if data.get('integration_id') else None
        endpoint = ChatbotEndpoint.objects.filter(id=data.get('endpoint_id'), tenant=tenant).first() if data.get('endpoint_id') else None
        bot_definition = ChatbotDefinition.objects.filter(id=data.get('bot_definition_id'), tenant=tenant).first() if data.get('bot_definition_id') else None

        event = ChatbotEventLog.objects.create(
            tenant=tenant,
            integration=integration,
            endpoint=endpoint,
            bot_definition=bot_definition,
            severity=data.get('severity', ChatbotEventLog.SEVERITY_INFO),
            event_type=data['event_type'],
            message=data.get('message', ''),
            payload_json=data.get('payload_json') or {},
            dedupe_key=data.get('dedupe_key', ''),
        )
        return Response({'ok': True, 'event_id': event.id})


class ChatbotMessageIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChatbotMessageIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get('workspace_id') is not None:
            tenant, workspace, _api_key = resolve_request_context(
                request,
                tenant_id=data.get('tenant_id'),
                workspace_id=data.get('workspace_id'),
            )
        else:
            api_key = get_api_key_from_header(request)
            if api_key is None:
                return Response({'detail': 'Authentication required.'}, status=401)
            tenant = api_key.tenant
            workspace = None

        integration = ChatbotIntegration.objects.get(id=data['integration_id'], tenant=tenant)
        endpoint = ChatbotEndpoint.objects.filter(id=data.get('endpoint_id'), tenant=tenant).first() if data.get('endpoint_id') else None
        bot_definition = ChatbotDefinition.objects.filter(id=data.get('bot_definition_id'), tenant=tenant).first() if data.get('bot_definition_id') else None

        conversation, _created = ChatbotConversation.objects.get_or_create(
            tenant=tenant,
            integration=integration,
            external_conversation_id=data.get('external_conversation_id', ''),
            external_thread_id=data.get('external_thread_id', ''),
            defaults={
                'workspace': workspace,
                'endpoint': endpoint,
                'bot_definition': bot_definition,
                'platform': data['platform'],
                'title': data.get('title', ''),
            },
        )
        conversation.workspace = workspace
        conversation.endpoint = endpoint
        conversation.bot_definition = bot_definition
        conversation.platform = data['platform']
        if data.get('title'):
            conversation.title = data['title']
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['workspace', 'endpoint', 'bot_definition', 'platform', 'title', 'last_message_at', 'updated_at'])

        message = ChatbotMessage.objects.create(
            conversation=conversation,
            direction=data['direction'],
            external_message_id=data.get('external_message_id', ''),
            sender_external_id=data.get('sender_external_id', ''),
            sender_label=data.get('sender_label', ''),
            body=data.get('body', ''),
            normalized_content_json=data.get('normalized_content_json') or {},
            retrieval_metadata_json=data.get('retrieval_metadata_json') or {},
            model_metadata_json=data.get('model_metadata_json') or {},
            delivery_status=data.get('delivery_status', ''),
        )
        return Response({'ok': True, 'conversation_id': conversation.id, 'message_id': message.id})
