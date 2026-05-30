from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from control.views import _dashboard_base, _handle_workspace_actions

from .forms import SupportChannelForm, SupportConversationUpdateForm, SupportReplyForm
from .models import SupportChannel, SupportContact, SupportConversation, SupportMessage


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
                messages.success(request, 'Reply draft saved locally. Twilio send wiring is the next step.')
                return redirect('support_conversation_detail', conversation_id=conversation.id)
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
