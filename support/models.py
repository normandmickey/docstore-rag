from django.contrib.auth import get_user_model
from django.db import models

from control.models import Tenant, Workspace

User = get_user_model()


class SupportChannel(models.Model):
    TYPE_SMS = 'sms'
    TYPE_VOICE = 'voice'
    TYPE_BOTH = 'both'
    TYPE_EMAIL = 'email'
    TYPE_CHOICES = [
        (TYPE_SMS, 'SMS'),
        (TYPE_VOICE, 'Voice'),
        (TYPE_BOTH, 'SMS + Voice'),
        (TYPE_EMAIL, 'Email'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='support_channels')
    default_workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_channels')
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SMS)
    twilio_phone_number = models.CharField(max_length=32, unique=True, db_index=True)
    twilio_phone_number_sid = models.CharField(max_length=64, blank=True, default='')
    active = models.BooleanField(default=True)
    ai_enabled = models.BooleanField(default=True)
    auto_reply_enabled = models.BooleanField(default=False)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'name']

    def __str__(self):
        return f'{self.tenant.name} :: {self.name}'


class SupportContact(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='support_contacts')
    phone_number = models.CharField(max_length=32, db_index=True, blank=True, default='')
    email = models.EmailField(blank=True, default='', db_index=True)
    name = models.CharField(max_length=255, blank=True, default='')
    external_ref = models.CharField(max_length=255, blank=True, default='')
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'email', 'phone_number']

    def __str__(self):
        return self.name or self.email or self.phone_number


class SupportConversation(models.Model):
    STATUS_OPEN = 'open'
    STATUS_PENDING = 'pending'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_CLOSED, 'Closed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='support_conversations')
    channel = models.ForeignKey(SupportChannel, on_delete=models.CASCADE, related_name='conversations')
    contact = models.ForeignKey(SupportContact, on_delete=models.CASCADE, related_name='conversations')
    workspace_context = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_conversations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    assigned_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_support_conversations')
    subject = models.CharField(max_length=255, blank=True, default='')
    latest_summary = models.TextField(blank=True, default='')
    last_message_at = models.DateTimeField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at', '-updated_at', '-id']

    def __str__(self):
        return f'{self.tenant.name} :: {self.contact} :: {self.status}'


class SupportMessage(models.Model):
    DIR_INBOUND = 'inbound'
    DIR_OUTBOUND = 'outbound'
    DIR_CHOICES = [
        (DIR_INBOUND, 'Inbound'),
        (DIR_OUTBOUND, 'Outbound'),
    ]

    KIND_SMS = 'sms'
    KIND_EMAIL = 'email'
    KIND_CALL_NOTE = 'call_note'
    KIND_VOICEMAIL = 'voicemail'
    KIND_SYSTEM = 'system'
    KIND_CHOICES = [
        (KIND_SMS, 'SMS'),
        (KIND_EMAIL, 'Email'),
        (KIND_CALL_NOTE, 'Call Note'),
        (KIND_VOICEMAIL, 'Voicemail'),
        (KIND_SYSTEM, 'System'),
    ]

    conversation = models.ForeignKey(SupportConversation, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=20, choices=DIR_CHOICES)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_SMS)
    body = models.TextField(blank=True, default='')
    provider_message_sid = models.CharField(max_length=64, blank=True, default='', db_index=True)
    delivery_status = models.CharField(max_length=40, blank=True, default='')
    sent_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_messages_sent')
    retrieval_metadata_json = models.JSONField(default=dict, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.conversation_id} :: {self.direction} :: {self.kind}'


class SupportCall(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='support_calls')
    channel = models.ForeignKey(SupportChannel, on_delete=models.CASCADE, related_name='calls')
    conversation = models.ForeignKey(SupportConversation, on_delete=models.CASCADE, related_name='calls')
    contact = models.ForeignKey(SupportContact, on_delete=models.CASCADE, related_name='calls')
    call_sid = models.CharField(max_length=64, unique=True, db_index=True)
    from_number = models.CharField(max_length=32, blank=True, default='')
    to_number = models.CharField(max_length=32, blank=True, default='')
    caller_name = models.CharField(max_length=255, blank=True, default='')
    recording_sid = models.CharField(max_length=64, blank=True, default='')
    recording_url = models.TextField(blank=True, default='')
    transcription_text = models.TextField(blank=True, default='')
    status = models.CharField(max_length=40, blank=True, default='')
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.call_sid} :: {self.from_number} -> {self.to_number}'


class TenantEmailIntegration(models.Model):
    PROVIDER_AGENTMAIL = 'agentmail'
    PROVIDER_CHOICES = [
        (PROVIDER_AGENTMAIL, 'AgentMail'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='email_integrations')
    default_workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='tenant_email_integrations')
    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES, default=PROVIDER_AGENTMAIL)
    label = models.CharField(max_length=200, default='Support Email')
    from_name = models.CharField(max_length=200, blank=True, default='')
    from_email = models.EmailField(blank=True, default='')
    inbox_id = models.CharField(max_length=255, blank=True, default='')
    api_key = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    auto_reply_enabled = models.BooleanField(default=False)
    metadata_json = models.JSONField(default=dict, blank=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True, default='')
    last_test_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'label']
        unique_together = [('tenant', 'provider')]

    def __str__(self):
        return f'{self.tenant.name} :: {self.label}'
