from django.db import transaction
from django.utils import timezone

from .models import SupportCall, SupportChannel, SupportContact, SupportConversation, SupportMessage


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


@transaction.atomic
def ingest_inbound_call(*, to_number: str, from_number: str, call_sid: str = '', caller_name: str = ''):
    to_number = normalize_phone_number(to_number)
    from_number = normalize_phone_number(from_number)
    call_sid = (call_sid or '').strip()
    caller_name = (caller_name or '').strip()

    existing_call = SupportCall.objects.select_related('conversation', 'channel', 'contact').filter(call_sid=call_sid).first() if call_sid else None
    if existing_call is not None:
        changed_fields = []
        if caller_name and not existing_call.caller_name:
            existing_call.caller_name = caller_name
            changed_fields.append('caller_name')
        if from_number and existing_call.from_number != from_number:
            existing_call.from_number = from_number
            changed_fields.append('from_number')
        if to_number and existing_call.to_number != to_number:
            existing_call.to_number = to_number
            changed_fields.append('to_number')
        if changed_fields:
            existing_call.save(update_fields=changed_fields + ['updated_at'])
        return existing_call.conversation, existing_call

    channel = SupportChannel.objects.select_related('tenant', 'default_workspace').filter(
        twilio_phone_number=to_number,
        active=True,
    ).first()
    if channel is None:
        raise SupportChannel.DoesNotExist(f'No active support channel found for {to_number}')

    contact, created = SupportContact.objects.get_or_create(
        tenant=channel.tenant,
        phone_number=from_number,
        defaults={'name': caller_name},
    )
    if caller_name and not contact.name:
        contact.name = caller_name
        contact.save(update_fields=['name', 'updated_at'])

    conversation = SupportConversation.objects.create(
        tenant=channel.tenant,
        channel=channel,
        contact=contact,
        workspace_context=channel.default_workspace,
        status=SupportConversation.STATUS_OPEN,
        subject='Inbound phone support request',
        last_message_at=timezone.now(),
        metadata_json={'source': 'voice'},
    )

    call = SupportCall.objects.create(
        tenant=channel.tenant,
        channel=channel,
        conversation=conversation,
        contact=contact,
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        caller_name=caller_name,
        status='in_progress',
        metadata_json={'contact_created': created},
    )

    SupportMessage.objects.create(
        conversation=conversation,
        direction=SupportMessage.DIR_INBOUND,
        kind=SupportMessage.KIND_CALL_NOTE,
        body='Inbound phone call received. Awaiting voicemail recording.',
        delivery_status='received',
        metadata_json={'call_sid': call_sid},
    )
    return conversation, call


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


def attach_voicemail_to_call(*, call_sid: str, recording_url: str = '', recording_sid: str = '', transcription_text: str = '', call_status: str = ''):
    call_sid = (call_sid or '').strip()
    if not call_sid:
        return None, None
    call = SupportCall.objects.select_related('conversation').filter(call_sid=call_sid).first()
    if call is None:
        return None, None
    changed_fields = []
    if recording_url:
        call.recording_url = recording_url.strip()
        changed_fields.append('recording_url')
    if recording_sid:
        call.recording_sid = recording_sid.strip()
        changed_fields.append('recording_sid')
    if transcription_text:
        call.transcription_text = transcription_text.strip()
        changed_fields.append('transcription_text')
    if call_status:
        call.status = call_status.strip()
        changed_fields.append('status')
    if changed_fields:
        call.save(update_fields=changed_fields + ['updated_at'])

    body_parts = ['Voicemail received from caller.']
    if transcription_text:
        body_parts.append('Transcript:')
        body_parts.append(transcription_text.strip())
    elif recording_url:
        body_parts.append(f'Recording: {recording_url.strip()}')

    message = SupportMessage.objects.create(
        conversation=call.conversation,
        direction=SupportMessage.DIR_INBOUND,
        kind=SupportMessage.KIND_VOICEMAIL,
        body='\n'.join(body_parts),
        delivery_status=call.status or 'completed',
        metadata_json={
            'call_sid': call.call_sid,
            'recording_sid': call.recording_sid,
            'recording_url': call.recording_url,
        },
    )
    call.conversation.last_message_at = message.created_at
    call.conversation.save(update_fields=['last_message_at', 'updated_at'])
    return call, message
