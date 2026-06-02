from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from control.agentmail import AgentMailClient, AgentMailError

from .models import SupportChannel, SupportContact, SupportConversation, SupportMessage, TenantEmailIntegration


class TenantEmailIntegrationError(Exception):
    pass


class TenantEmailClient:
    def __init__(self, integration: TenantEmailIntegration):
        self.integration = integration
        if not integration.api_key:
            raise TenantEmailIntegrationError('AgentMail API key is not configured for this tenant email integration.')
        if not integration.inbox_id:
            raise TenantEmailIntegrationError('AgentMail inbox id is not configured for this tenant email integration.')
        self.client = AgentMailClient(api_key=integration.api_key, inbox_id=integration.inbox_id)

    @classmethod
    def for_tenant(cls, tenant):
        integration = TenantEmailIntegration.objects.filter(
            tenant=tenant,
            provider=TenantEmailIntegration.PROVIDER_AGENTMAIL,
            status=TenantEmailIntegration.STATUS_ACTIVE,
        ).first()
        if integration is None:
            raise TenantEmailIntegrationError('No active tenant email integration is configured.')
        return cls(integration)

    def send_message(self, *, to_email: str, subject: str, text: str, html: str = '') -> dict:
        try:
            return self.client.send_message(to=to_email, subject=subject, text=text, html=html)
        except AgentMailError as exc:
            raise TenantEmailIntegrationError(str(exc)) from exc


@transaction.atomic
def ingest_inbound_email(*, integration: TenantEmailIntegration, from_email: str, from_name: str = '', subject: str = '', body_text: str = '', provider_message_id: str = ''):
    from_email = (from_email or '').strip().lower()
    from_name = (from_name or '').strip()
    subject = (subject or '').strip()
    body_text = (body_text or '').strip()
    provider_message_id = (provider_message_id or '').strip()

    if not from_email:
        raise TenantEmailIntegrationError('Inbound email is missing sender email address.')

    channel, _created = SupportChannel.objects.get_or_create(
        tenant=integration.tenant,
        twilio_phone_number=f'email:{integration.id}',
        defaults={
            'name': integration.label or 'Support Email',
            'channel_type': SupportChannel.TYPE_EMAIL,
            'default_workspace': integration.default_workspace,
            'active': integration.status == TenantEmailIntegration.STATUS_ACTIVE,
            'ai_enabled': True,
            'auto_reply_enabled': integration.auto_reply_enabled,
            'metadata_json': {
                'provider': integration.provider,
                'integration_id': integration.id,
                'from_email': integration.from_email,
            },
        },
    )
    if channel.default_workspace_id != integration.default_workspace_id or channel.active != (integration.status == TenantEmailIntegration.STATUS_ACTIVE) or channel.auto_reply_enabled != integration.auto_reply_enabled:
        channel.default_workspace = integration.default_workspace
        channel.active = integration.status == TenantEmailIntegration.STATUS_ACTIVE
        channel.auto_reply_enabled = integration.auto_reply_enabled
        channel.channel_type = SupportChannel.TYPE_EMAIL
        channel.metadata_json = {
            **(channel.metadata_json or {}),
            'provider': integration.provider,
            'integration_id': integration.id,
            'from_email': integration.from_email,
        }
        channel.save(update_fields=['default_workspace', 'active', 'auto_reply_enabled', 'channel_type', 'metadata_json', 'updated_at'])

    contact, _contact_created = SupportContact.objects.get_or_create(
        tenant=integration.tenant,
        email=from_email,
        defaults={
            'name': from_name,
            'metadata_json': {},
        },
    )
    if from_name and not contact.name:
        contact.name = from_name
        contact.save(update_fields=['name', 'updated_at'])

    conversation = SupportConversation.objects.filter(
        tenant=integration.tenant,
        channel=channel,
        contact=contact,
        status__in=[SupportConversation.STATUS_OPEN, SupportConversation.STATUS_PENDING],
    ).order_by('-last_message_at', '-updated_at', '-id').first()

    if conversation is None:
        conversation = SupportConversation.objects.create(
            tenant=integration.tenant,
            channel=channel,
            contact=contact,
            workspace_context=integration.default_workspace,
            status=SupportConversation.STATUS_OPEN,
            subject=subject[:255],
            last_message_at=timezone.now(),
            metadata_json={'source': 'email', 'integration_id': integration.id},
        )

    message = SupportMessage.objects.create(
        conversation=conversation,
        direction=SupportMessage.DIR_INBOUND,
        kind=SupportMessage.KIND_EMAIL,
        body=body_text,
        provider_message_sid=provider_message_id,
        delivery_status='received',
        metadata_json={
            'subject': subject,
            'from_email': from_email,
            'from_name': from_name,
            'integration_id': integration.id,
        },
    )
    conversation.last_message_at = message.created_at
    if conversation.status == SupportConversation.STATUS_CLOSED:
        conversation.status = SupportConversation.STATUS_OPEN
    if not conversation.workspace_context_id and integration.default_workspace_id:
        conversation.workspace_context = integration.default_workspace
    conversation.save(update_fields=['last_message_at', 'status', 'workspace_context', 'updated_at'])
    return conversation, message
