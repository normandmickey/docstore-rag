from django.db import transaction
from django.utils import timezone

from .models import SupportChannel, SupportContact, SupportConversation, SupportMessage


def normalize_phone_number(phone_number: str) -> str:
    return ''.join(ch for ch in (phone_number or '').strip() if ch.isdigit() or ch == '+')


@transaction.atomic
def ingest_inbound_sms(*, to_number: str, from_number: str, body: str, provider_message_sid: str = '', profile_name: str = ''):
    to_number = normalize_phone_number(to_number)
    from_number = normalize_phone_number(from_number)
    provider_message_sid = (provider_message_sid or '').strip()
    body = (body or '').strip()
    profile_name = (profile_name or '').strip()

    channel = SupportChannel.objects.select_related('tenant', 'default_workspace').filter(
        twilio_phone_number=to_number,
        active=True,
    ).first()
    if channel is None:
        raise SupportChannel.DoesNotExist(f'No active support channel found for {to_number}')

    contact, created = SupportContact.objects.get_or_create(
        tenant=channel.tenant,
        phone_number=from_number,
        defaults={
            'name': profile_name,
        },
    )
    if profile_name and not contact.name:
        contact.name = profile_name
        contact.save(update_fields=['name', 'updated_at'])

    conversation = SupportConversation.objects.filter(
        tenant=channel.tenant,
        channel=channel,
        contact=contact,
        status__in=[SupportConversation.STATUS_OPEN, SupportConversation.STATUS_PENDING],
    ).order_by('-last_message_at', '-updated_at', '-id').first()

    if conversation is None:
        conversation = SupportConversation.objects.create(
            tenant=channel.tenant,
            channel=channel,
            contact=contact,
            workspace_context=channel.default_workspace,
            status=SupportConversation.STATUS_OPEN,
            subject=(body[:120] if body else ''),
            last_message_at=timezone.now(),
        )

    message = SupportMessage.objects.create(
        conversation=conversation,
        direction=SupportMessage.DIR_INBOUND,
        kind=SupportMessage.KIND_SMS,
        body=body,
        provider_message_sid=provider_message_sid,
        delivery_status='received',
        metadata_json={
            'profile_name': profile_name,
            'contact_created': created,
        },
    )
    conversation.last_message_at = message.created_at
    if conversation.status == SupportConversation.STATUS_CLOSED:
        conversation.status = SupportConversation.STATUS_OPEN
    if not conversation.workspace_context_id and channel.default_workspace_id:
        conversation.workspace_context = channel.default_workspace
    conversation.save(update_fields=['last_message_at', 'status', 'workspace_context', 'updated_at'])
    return conversation, message


def update_message_delivery_status(*, provider_message_sid: str, delivery_status: str):
    provider_message_sid = (provider_message_sid or '').strip()
    delivery_status = (delivery_status or '').strip()
    if not provider_message_sid:
        return None
    message = SupportMessage.objects.filter(provider_message_sid=provider_message_sid).first()
    if message is None:
        return None
    message.delivery_status = delivery_status
    message.save(update_fields=['delivery_status'])
    return message
