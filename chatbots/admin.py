from django.contrib import admin

from .models import (
    ChatbotBuild,
    ChatbotConversation,
    ChatbotDefinition,
    ChatbotDeployment,
    ChatbotEndpoint,
    ChatbotEndpointBinding,
    ChatbotEventLog,
    ChatbotIntegration,
    ChatbotMessage,
)


@admin.register(ChatbotIntegration)
class ChatbotIntegrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'platform', 'status', 'active', 'updated_at')
    list_filter = ('platform', 'status', 'active', 'tenant')
    search_fields = ('name', 'external_app_id', 'external_bot_id')


@admin.register(ChatbotEndpoint)
class ChatbotEndpointAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'tenant', 'integration', 'endpoint_type', 'mode', 'default_workspace', 'active')
    list_filter = ('endpoint_type', 'mode', 'active', 'tenant', 'integration')
    search_fields = ('display_name', 'external_id', 'external_parent_id')


@admin.register(ChatbotDefinition)
class ChatbotDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'integration', 'default_workspace', 'runtime_mode', 'active', 'updated_at')
    list_filter = ('runtime_mode', 'active', 'tenant', 'integration')
    search_fields = ('name', 'slug', 'template_name')


@admin.register(ChatbotEndpointBinding)
class ChatbotEndpointBindingAdmin(admin.ModelAdmin):
    list_display = ('bot_definition', 'endpoint', 'workspace_override', 'active', 'updated_at')
    list_filter = ('active', 'workspace_override')
    search_fields = ('bot_definition__name', 'endpoint__display_name')


@admin.register(ChatbotBuild)
class ChatbotBuildAdmin(admin.ModelAdmin):
    list_display = ('bot_definition', 'version', 'status', 'artifact_type', 'created_by', 'created_at')
    list_filter = ('status', 'artifact_type', 'created_at')
    search_fields = ('bot_definition__name', 'artifact_path')


@admin.register(ChatbotDeployment)
class ChatbotDeploymentAdmin(admin.ModelAdmin):
    list_display = ('bot_definition', 'build', 'runner_type', 'runner_target', 'status', 'last_heartbeat_at')
    list_filter = ('status', 'runner_type', 'created_at')
    search_fields = ('bot_definition__name', 'runner_target')


@admin.register(ChatbotConversation)
class ChatbotConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'tenant', 'workspace', 'platform', 'integration', 'bot_definition', 'status', 'last_message_at')
    list_filter = ('platform', 'status', 'tenant', 'integration')
    search_fields = ('title', 'external_conversation_id', 'external_thread_id')


@admin.register(ChatbotMessage)
class ChatbotMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'direction', 'sender_label', 'delivery_status', 'created_at')
    list_filter = ('direction', 'delivery_status', 'created_at')
    search_fields = ('conversation__title', 'external_message_id', 'sender_label', 'body')


@admin.register(ChatbotEventLog)
class ChatbotEventLogAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'event_type', 'severity', 'integration', 'endpoint', 'created_at')
    list_filter = ('severity', 'event_type', 'tenant', 'integration', 'created_at')
    search_fields = ('message', 'event_type', 'dedupe_key')
