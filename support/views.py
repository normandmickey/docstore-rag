import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from control.views import _dashboard_base, _handle_workspace_actions

from .forms import SupportChannelForm, SupportConversationUpdateForm, SupportReplyForm
from .models import SupportChannel, SupportContact, SupportConversation, SupportMessage
from .services import ingest_inbound_sms, update_message_delivery_status
from .twilio import TwilioRestException, send_sms, twilio_enabled, validate_twilio_request

logger = logging.getLogger(__name__)


@login_required
def support_index(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')

    status_filter = (request.GET.get('status') or 'open').strip().lower()
    valid_statuses = {choice[0] for choice in SupportConversation.STATUS_CHOICES}
    if status_filter not in valid_statuses and status_filter != 'all':
        status_filter = 'open'

    conversations = SupportConversation.objects.select_related(
        'tenant', 'channel', 'contact', 'workspace_context', 'assigned_user'
    ).filter(tenant=tenant)
    if status_filter != 'all':
        conversations = conversations.filter(status=status_filter)

    base.update({
        'section': 'support',
        'support_status_filter': status_filter,
        'support_conversations': conversations.order_by('-last_message_at', '-updated_at', '-id')[:100],
        'support_channels_count': SupportChannel.objects.filter(tenant=tenant, active=True).count(),
        'support_contacts_count': SupportContact.objects.filter(tenant=tenant).count(),
    })
    return render(request, 'dashboard/support_index.html', base)


@login_required
def support_channels(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage support channels.')
        return redirect('support_index')

    base.update({
        'section': 'support',
        'support_subsection': 'channels',
        'support_channels': SupportChannel.objects.filter(tenant=tenant).select_related('default_workspace').order_by('name'),
    })
    return render(request, 'dashboard/support_channels.html', base)


@login_required
def support_channel_new(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage support channels.')
        return redirect('support_index')

    if request.method == 'POST':
        form = SupportChannelForm(request.POST, tenant=tenant)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.tenant = tenant
            channel.save()
            messages.success(request, 'Support channel created.')
            return redirect('support_channels')
    else:
        form = SupportChannelForm(tenant=tenant)

    base.update({
        'section': 'support',
        'support_subsection': 'channels',
        'support_channel_form': form,
        'support_channel_mode': 'new',
    })
    return render(request, 'dashboard/support_channel_form.html', base)


@login_required
def support_channel_edit(request, channel_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage support channels.')
        return redirect('support_index')

    channel = get_object_or_404(SupportChannel, id=channel_id, tenant=tenant)
    if request.method == 'POST':
        form = SupportChannelForm(request.POST, instance=channel, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Support channel updated.')
            return redirect('support_channels')
    else:
        form = SupportChannelForm(instance=channel, tenant=tenant)

    base.update({
        'section': 'support',
        'support_subsection': 'channels',
        'support_channel_form': form,
        'support_channel': channel,
        'support_channel_mode': 'edit',
    })
    return render(request, 'dashboard/support_channel_form.html', base)


@login_required
def support_conversation_detail(request, conversation_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')

    conversation = get_object_or_404(
        SupportConversation.objects.select_related('tenant', 'channel', 'contact', 'workspace_context', 'assigned_user'),
        id=conversation_id,
        tenant=tenant,
    )

    if request.method == 'POST' and request.POST.get('action') == 'reply':
        reply_form = SupportReplyForm(request.POST)
        update_form = SupportConversationUpdateForm(instance=conversation, tenant=tenant)
        if reply_form.is_valid():
            body = (reply_form.cleaned_data.get('body') or '').strip()
            if body:
                if not twilio_enabled():
                    SupportMessage.objects.create(
                        conversation=conversation,
                        direction=SupportMessage.DIR_OUTBOUND,
                        kind=SupportMessage.KIND_SYSTEM,
                        body=body,
                        sent_by_user=request.user,
                        delivery_status='draft',
                    )
                    conversation.last_message_at = timezone.now()
                    if conversation.status == SupportConversation.STATUS_CLOSED:
                        conversation.status = SupportConversation.STATUS_OPEN
                    conversation.save(update_fields=['last_message_at', 'status', 'updated_at'])
                    messages.warning(request, 'Twilio is not configured yet, so this reply was saved as a local draft only.')
                    return redirect('support_conversation_detail', conversation_id=conversation.id)

                try:
                    provider_message = send_sms(
                        from_number=conversation.channel.twilio_phone_number,
                        to_number=conversation.contact.phone_number,
                        body=body,
                    )
                    SupportMessage.objects.create(
                        conversation=conversation,
                        direction=SupportMessage.DIR_OUTBOUND,
                        kind=SupportMessage.KIND_SMS,
                        body=body,
                        sent_by_user=request.user,
                        provider_message_sid=getattr(provider_message, 'sid', '') or '',
                        delivery_status=getattr(provider_message, 'status', '') or 'queued',
                        metadata_json={
                            'twilio_from': conversation.channel.twilio_phone_number,
                            'twilio_to': conversation.contact.phone_number,
                        },
                    )
                    conversation.last_message_at = timezone.now()
                    if conversation.status == SupportConversation.STATUS_CLOSED:
                        conversation.status = SupportConversation.STATUS_OPEN
                    conversation.save(update_fields=['last_message_at', 'status', 'updated_at'])
                    messages.success(request, 'Reply sent via Twilio.')
                    return redirect('support_conversation_detail', conversation_id=conversation.id)
                except TwilioRestException as exc:
                    messages.error(request, f'Twilio send failed: {exc}')
                except Exception as exc:
                    messages.error(request, f'Unexpected send error: {exc}')
    elif request.method == 'POST' and request.POST.get('action') == 'update_conversation':
        update_form = SupportConversationUpdateForm(request.POST, instance=conversation, tenant=tenant)
        reply_form = SupportReplyForm()
        if update_form.is_valid():
            update_form.save()
            messages.success(request, 'Conversation updated.')
            return redirect('support_conversation_detail', conversation_id=conversation.id)
    else:
        reply_form = SupportReplyForm()
        update_form = SupportConversationUpdateForm(instance=conversation, tenant=tenant)

    base.update({
        'section': 'support',
        'support_subsection': 'conversation',
        'support_conversation': conversation,
        'support_messages': conversation.messages.select_related('sent_by_user').order_by('created_at', 'id'),
        'support_reply_form': reply_form,
        'support_update_form': update_form,
    })
    return render(request, 'dashboard/support_conversation.html', base)


@csrf_exempt
@require_POST
def twilio_sms_inbound(request):
    to_number = request.POST.get('To', '')
    from_number = request.POST.get('From', '')
    message_sid = request.POST.get('MessageSid', '')
    logger.info('Twilio inbound webhook hit to=%s from=%s sid=%s', to_number, from_number, message_sid)

    if not validate_twilio_request(request):
        logger.warning('Twilio inbound signature validation failed to=%s from=%s sid=%s url=%s', to_number, from_number, message_sid, request.build_absolute_uri())
        return HttpResponse(status=403)

    body = request.POST.get('Body', '')
    profile_name = request.POST.get('ProfileName', '')

    if not to_number or not from_number:
        logger.warning('Twilio inbound missing To/From sid=%s', message_sid)
        return HttpResponseBadRequest('Missing To/From')

    try:
        conversation, message = ingest_inbound_sms(
            to_number=to_number,
            from_number=from_number,
            body=body,
            provider_message_sid=message_sid,
            profile_name=profile_name,
        )
        logger.info('Twilio inbound stored conversation_id=%s message_id=%s sid=%s', conversation.id, message.id, message_sid)
    except SupportChannel.DoesNotExist:
        logger.warning('Twilio inbound no support channel found to=%s from=%s sid=%s', to_number, from_number, message_sid)
        return HttpResponse(status=404)
    except Exception:
        logger.exception('Twilio inbound ingest failed to=%s from=%s sid=%s', to_number, from_number, message_sid)
        return HttpResponse(status=500)

    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', content_type='text/xml')


@csrf_exempt
@require_POST
def twilio_sms_status(request):
    message_sid = request.POST.get('MessageSid', '')
    message_status = request.POST.get('MessageStatus', '')
    if not validate_twilio_request(request):
        logger.warning('Twilio status signature validation failed sid=%s status=%s url=%s', message_sid, message_status, request.build_absolute_uri())
        return HttpResponse(status=403)

    update_message_delivery_status(provider_message_sid=message_sid, delivery_status=message_status)
    logger.info('Twilio status updated sid=%s status=%s', message_sid, message_status)
    return HttpResponse('ok')
