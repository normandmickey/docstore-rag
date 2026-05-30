import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from control.models import Tenant, Workspace


class ChatbotIntegration(models.Model):
    PLATFORM_TELEGRAM = 'telegram'
    PLATFORM_DISCORD = 'discord'
    PLATFORM_ZOOM_CHAT = 'zoom_chat'
    PLATFORM_ZOOM_MEETING = 'zoom_meeting'
    PLATFORM_CHOICES = [
        (PLATFORM_TELEGRAM, 'Telegram'),
        (PLATFORM_DISCORD, 'Discord'),
        (PLATFORM_ZOOM_CHAT, 'Zoom Chat'),
        (PLATFORM_ZOOM_MEETING, 'Zoom Meeting'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ERROR = 'error'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ERROR, 'Error'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='chatbot_integrations')
    platform = models.CharField(max_length=32, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    active = models.BooleanField(default=True)
    external_app_id = models.CharField(max_length=255, blank=True, default='')
    external_bot_id = models.CharField(max_length=255, blank=True, default='')
    webhook_url = models.URLField(blank=True, default='')
    webhook_status = models.CharField(max_length=64, blank=True, default='')
    runner_key = models.CharField(max_length=64, blank=True, default='', db_index=True)
    credentials_json = models.JSONField(default=dict, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'platform', 'name']

    def save(self, *args, **kwargs):
        if not self.runner_key:
            self.runner_key = secrets.token_urlsafe(18)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.tenant.name} :: {self.name} ({self.platform})'


class ChatbotEndpoint(models.Model):
    TYPE_DM = 'dm'
    TYPE_GROUP = 'group'
    TYPE_CHANNEL = 'channel'
    TYPE_THREAD = 'thread'
    TYPE_MEETING = 'meeting'
    TYPE_CHAT_ROOM = 'chat_room'
    TYPE_CHOICES = [
        (TYPE_DM, 'Direct Message'),
        (TYPE_GROUP, 'Group'),
        (TYPE_CHANNEL, 'Channel'),
        (TYPE_THREAD, 'Thread'),
        (TYPE_MEETING, 'Meeting'),
        (TYPE_CHAT_ROOM, 'Chat Room'),
    ]

    MODE_DM_ONLY = 'dm_only'
    MODE_MENTION_ONLY = 'mention_only'
    MODE_ALWAYS_ON = 'always_on'
    MODE_MEETING_ASSISTANT = 'meeting_assistant'
    MODE_CHOICES = [
        (MODE_DM_ONLY, 'DM only'),
        (MODE_MENTION_ONLY, 'Mention only'),
        (MODE_ALWAYS_ON, 'Always on'),
        (MODE_MEETING_ASSISTANT, 'Meeting assistant'),
    ]

    integration = models.ForeignKey(ChatbotIntegration, on_delete=models.CASCADE, related_name='endpoints')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='chatbot_endpoints')
    endpoint_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    external_id = models.CharField(max_length=255)
    external_parent_id = models.CharField(max_length=255, blank=True, default='')
    display_name = models.CharField(max_length=255)
    default_workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_endpoints')
    mode = models.CharField(max_length=32, choices=MODE_CHOICES, default=MODE_MENTION_ONLY)
    active = models.BooleanField(default=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'display_name']
        unique_together = [('integration', 'external_id')]

    def __str__(self):
        return f'{self.integration.name} :: {self.display_name}'


class ChatbotDefinition(models.Model):
    RUNTIME_SHARED = 'shared_runner'
    RUNTIME_ISOLATED = 'isolated_runner'
    RUNTIME_CHOICES = [
        (RUNTIME_SHARED, 'Shared runner'),
        (RUNTIME_ISOLATED, 'Isolated runner'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='chatbot_definitions')
    integration = models.ForeignKey(ChatbotIntegration, on_delete=models.CASCADE, related_name='definitions')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    default_workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_definitions')
    persona_prompt = models.TextField(blank=True, default='')
    system_prompt = models.TextField(blank=True, default='')
    runtime_mode = models.CharField(max_length=32, choices=RUNTIME_CHOICES, default=RUNTIME_SHARED)
    template_name = models.CharField(max_length=120, blank=True, default='')
    template_version = models.CharField(max_length=64, blank=True, default='')
    allowed_tools_json = models.JSONField(default=dict, blank=True)
    response_policy_json = models.JSONField(default=dict, blank=True)
    handoff_policy_json = models.JSONField(default=dict, blank=True)
    logging_policy_json = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'name']
        unique_together = [('tenant', 'slug')]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'chatbot'
            slug = base_slug
            i = 2
            while ChatbotDefinition.objects.exclude(pk=self.pk).filter(tenant=self.tenant, slug=slug).exists():
                slug = f'{base_slug}-{i}'
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.tenant.name} :: {self.name}'


class ChatbotEndpointBinding(models.Model):
    bot_definition = models.ForeignKey(ChatbotDefinition, on_delete=models.CASCADE, related_name='endpoint_bindings')
    endpoint = models.ForeignKey(ChatbotEndpoint, on_delete=models.CASCADE, related_name='bot_bindings')
    workspace_override = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_endpoint_bindings')
    active = models.BooleanField(default=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('bot_definition', 'endpoint')]
        ordering = ['bot_definition__name', 'endpoint__display_name']

    def __str__(self):
        return f'{self.bot_definition.name} -> {self.endpoint.display_name}'


class ChatbotBuild(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_BUILDING = 'building'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_DEPLOYED = 'deployed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_BUILDING, 'Building'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DEPLOYED, 'Deployed'),
    ]

    ARTIFACT_CONFIG = 'config'
    ARTIFACT_TEMPLATE_BUNDLE = 'template_bundle'
    ARTIFACT_CHOICES = [
        (ARTIFACT_CONFIG, 'Config'),
        (ARTIFACT_TEMPLATE_BUNDLE, 'Template bundle'),
    ]

    bot_definition = models.ForeignKey(ChatbotDefinition, on_delete=models.CASCADE, related_name='builds')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    artifact_type = models.CharField(max_length=32, choices=ARTIFACT_CHOICES, default=ARTIFACT_CONFIG)
    artifact_path = models.CharField(max_length=500, blank=True, default='')
    generated_manifest_json = models.JSONField(default=dict, blank=True)
    build_log = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_builds_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('bot_definition', 'version')]

    def __str__(self):
        return f'{self.bot_definition.name} build v{self.version}'


class ChatbotDeployment(models.Model):
    bot_definition = models.ForeignKey(ChatbotDefinition, on_delete=models.CASCADE, related_name='deployments')
    build = models.ForeignKey(ChatbotBuild, on_delete=models.CASCADE, related_name='deployments')
    runner_type = models.CharField(max_length=64, blank=True, default='')
    runner_target = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=64, blank=True, default='')
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.bot_definition.name} deployment ({self.status or "unknown"})'


class ChatbotConversation(models.Model):
    STATUS_OPEN = 'open'
    STATUS_ARCHIVED = 'archived'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_ARCHIVED, 'Archived'),
        (STATUS_CLOSED, 'Closed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='chatbot_conversations')
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_conversations')
    integration = models.ForeignKey(ChatbotIntegration, on_delete=models.CASCADE, related_name='conversations')
    endpoint = models.ForeignKey(ChatbotEndpoint, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    bot_definition = models.ForeignKey(ChatbotDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    platform = models.CharField(max_length=32, choices=ChatbotIntegration.PLATFORM_CHOICES)
    external_conversation_id = models.CharField(max_length=255, blank=True, default='')
    external_thread_id = models.CharField(max_length=255, blank=True, default='')
    title = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    last_message_at = models.DateTimeField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at', '-updated_at', '-id']

    def __str__(self):
        return self.title or f'{self.tenant.name} :: {self.platform}'


class ChatbotMessage(models.Model):
    DIR_INBOUND = 'inbound'
    DIR_OUTBOUND = 'outbound'
    DIR_SYSTEM = 'system'
    DIR_CHOICES = [
        (DIR_INBOUND, 'Inbound'),
        (DIR_OUTBOUND, 'Outbound'),
        (DIR_SYSTEM, 'System'),
    ]

    conversation = models.ForeignKey(ChatbotConversation, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=20, choices=DIR_CHOICES)
    external_message_id = models.CharField(max_length=255, blank=True, default='')
    sender_external_id = models.CharField(max_length=255, blank=True, default='')
    sender_label = models.CharField(max_length=255, blank=True, default='')
    body = models.TextField(blank=True, default='')
    normalized_content_json = models.JSONField(default=dict, blank=True)
    retrieval_metadata_json = models.JSONField(default=dict, blank=True)
    model_metadata_json = models.JSONField(default=dict, blank=True)
    delivery_status = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.conversation_id} :: {self.direction}'


class ChatbotEventLog(models.Model):
    SEVERITY_INFO = 'info'
    SEVERITY_WARNING = 'warning'
    SEVERITY_ERROR = 'error'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Info'),
        (SEVERITY_WARNING, 'Warning'),
        (SEVERITY_ERROR, 'Error'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='chatbot_event_logs')
    integration = models.ForeignKey(ChatbotIntegration, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_logs')
    endpoint = models.ForeignKey(ChatbotEndpoint, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_logs')
    bot_definition = models.ForeignKey(ChatbotDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_logs')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_INFO)
    event_type = models.CharField(max_length=120)
    message = models.TextField(blank=True, default='')
    payload_json = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tenant.name} :: {self.event_type} :: {self.severity}'
