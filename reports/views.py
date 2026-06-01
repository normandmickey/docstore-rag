from datetime import timedelta
from io import BytesIO

from django import forms

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from openpyxl import Workbook

from control.views import _dashboard_base, _handle_workspace_actions
from support.models import SupportChannel, SupportConversation, SupportMessage
from integrations.voice.models import VoiceCallRecord
from chatbots.models import ChatbotConversation, ChatbotIntegration
from .spreadsheet_transform import (
    SpreadsheetTransformError,
    apply_transform_plan,
    export_transform_csv,
    export_transform_xlsx,
    load_tabular_file,
    plan_transform,
)


class SpreadsheetTransformForm(forms.Form):
    file = forms.FileField(required=False)
    transform_request = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), help_text='Describe the columns and layout you want in the exported file.')
    export_format = forms.ChoiceField(choices=[('xlsx', 'XLSX'), ('csv', 'CSV')], initial='xlsx')
    strict_sanitization = forms.BooleanField(required=False, initial=False, help_text='Use more aggressive prompt-side masking for sample rows before AI planning.')


def _infer_support_source(conversation):
    meta = conversation.metadata_json or {}
    source = (meta.get('source') or '').strip().lower()
    if source == 'voice':
        return 'voice'
    if conversation.channel_id:
        channel_type = (conversation.channel.channel_type or '').strip().lower()
        if channel_type == 'voice':
            return 'voice'
        if channel_type == 'sms':
            return 'sms'
        if channel_type == 'both':
            return 'sms/voice'
    return 'support'


@login_required
def spreadsheet_transformer(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    base['section'] = 'reports'
    base['report_name'] = 'spreadsheet_transformer'
    base['spreadsheet_transform_form'] = SpreadsheetTransformForm()
    base['spreadsheet_transform_preview_headers'] = []
    base['spreadsheet_transform_preview_rows'] = []
    base['spreadsheet_transform_plan'] = None
    base['spreadsheet_transform_detected_fields'] = {}
    base['spreadsheet_transform_sanitized_samples'] = []
    base['spreadsheet_transform_prompt_preview'] = None

    if request.method == 'POST':
        action = (request.POST.get('action') or 'preview').strip()
        form = SpreadsheetTransformForm(request.POST, request.FILES)
        base['spreadsheet_transform_form'] = form
        if form.is_valid():
            try:
                session_table = request.session.get('spreadsheet_transform_table') or {}
                session_result = request.session.get('spreadsheet_transform_result') or {}

                if action == 'preview':
                    if not form.cleaned_data.get('file'):
                        raise SpreadsheetTransformError('Please upload a CSV or XLSX file to preview the transform.')
                    table = load_tabular_file(form.cleaned_data['file'])
                    plan, detected_fields, sanitized_samples, prompt_preview = plan_transform(
                        headers=table['headers'],
                        rows=table['rows'],
                        user_request=form.cleaned_data['transform_request'],
                        strict_sanitization=form.cleaned_data.get('strict_sanitization') or False,
                    )
                    headers, transformed_rows = apply_transform_plan(rows=table['rows'], plan=plan)
                    request.session['spreadsheet_transform_table'] = table
                    request.session['spreadsheet_transform_result'] = {
                        'plan': plan,
                        'detected_fields': detected_fields,
                        'sanitized_samples': sanitized_samples,
                        'prompt_preview': prompt_preview,
                        'headers': headers,
                        'rows': transformed_rows,
                        'export_format': form.cleaned_data['export_format'],
                        'strict_sanitization': form.cleaned_data.get('strict_sanitization') or False,
                        'transform_request': form.cleaned_data['transform_request'],
                    }
                    request.session.modified = True
                    session_result = request.session['spreadsheet_transform_result']
                    base['spreadsheet_transform_form'] = SpreadsheetTransformForm(initial={
                        'transform_request': session_result.get('transform_request', ''),
                        'export_format': session_result.get('export_format', 'xlsx'),
                        'strict_sanitization': session_result.get('strict_sanitization', False),
                    })

                elif action == 'download':
                    if not session_result:
                        raise SpreadsheetTransformError('No preview is available yet. Run a preview first.')
                    headers = session_result.get('headers') or []
                    transformed_rows = session_result.get('rows') or []
                    export_format = form.cleaned_data['export_format'] or session_result.get('export_format') or 'xlsx'
                    if export_format == 'csv':
                        payload = export_transform_csv(headers, transformed_rows)
                        response = HttpResponse(payload, content_type='text/csv')
                        response['Content-Disposition'] = 'attachment; filename="spreadsheet-transform.csv"'
                        return response
                    payload = export_transform_xlsx(headers, transformed_rows)
                    response = HttpResponse(
                        payload,
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    )
                    response['Content-Disposition'] = 'attachment; filename="spreadsheet-transform.xlsx"'
                    return response

                if session_result:
                    base['spreadsheet_transform_plan'] = session_result.get('plan')
                    base['spreadsheet_transform_detected_fields'] = session_result.get('detected_fields', {})
                    base['spreadsheet_transform_sanitized_samples'] = session_result.get('sanitized_samples', [])
                    base['spreadsheet_transform_prompt_preview'] = session_result.get('prompt_preview')
                    base['spreadsheet_transform_preview_headers'] = session_result.get('headers', [])
                    base['spreadsheet_transform_preview_rows'] = (session_result.get('rows') or [])[:20]
            except SpreadsheetTransformError as exc:
                messages.error(request, str(exc))
            except Exception as exc:
                messages.error(request, f'Spreadsheet transform failed: {exc}')

    return render(request, 'dashboard/spreadsheet_transformer.html', base)


@login_required
def support_activity_report(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')

    today = timezone.localdate()
    start_default = today - timedelta(days=29)
    start_raw = (request.GET.get('start') or '').strip()
    end_raw = (request.GET.get('end') or '').strip()

    try:
        start_date = timezone.datetime.fromisoformat(start_raw).date() if start_raw else start_default
    except ValueError:
        start_date = start_default
    try:
        end_date = timezone.datetime.fromisoformat(end_raw).date() if end_raw else today
    except ValueError:
        end_date = today

    if end_date < start_date:
        start_date, end_date = end_date, start_date

    start_dt = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
    end_dt = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))

    channel_id_raw = (request.GET.get('channel') or '').strip()
    assigned_user_id_raw = (request.GET.get('assigned_user') or '').strip()
    channel_id = int(channel_id_raw) if channel_id_raw.isdigit() else None
    assigned_user_id = int(assigned_user_id_raw) if assigned_user_id_raw.isdigit() else None

    conversations = SupportConversation.objects.filter(tenant=tenant, created_at__gte=start_dt, created_at__lte=end_dt)
    messages_qs = SupportMessage.objects.filter(conversation__tenant=tenant, created_at__gte=start_dt, created_at__lte=end_dt)
    calls_qs = VoiceCallRecord.objects.filter(tenant=tenant, created_at__gte=start_dt, created_at__lte=end_dt)

    if channel_id:
        conversations = conversations.filter(channel_id=channel_id)
        messages_qs = messages_qs.filter(conversation__channel_id=channel_id)
        calls_qs = calls_qs.filter(support_channel_id=channel_id)
    if assigned_user_id:
        conversations = conversations.filter(assigned_user_id=assigned_user_id)
        messages_qs = messages_qs.filter(conversation__assigned_user_id=assigned_user_id)
        calls_qs = calls_qs.filter(related_conversation__assigned_user_id=assigned_user_id)

    rows = []
    cursor = start_date
    while cursor <= end_date:
        next_day = cursor + timedelta(days=1)
        day_start = timezone.make_aware(timezone.datetime.combine(cursor, timezone.datetime.min.time()))
        day_end = timezone.make_aware(timezone.datetime.combine(cursor, timezone.datetime.max.time()))
        day_conversations = conversations.filter(created_at__gte=day_start, created_at__lte=day_end)
        rows.append({
            'date': cursor.isoformat(),
            'conversations_created': day_conversations.count(),
            'open_count': day_conversations.filter(status=SupportConversation.STATUS_OPEN).count(),
            'pending_count': day_conversations.filter(status=SupportConversation.STATUS_PENDING).count(),
            'closed_count': day_conversations.filter(status=SupportConversation.STATUS_CLOSED).count(),
            'messages_inbound': messages_qs.filter(created_at__gte=day_start, created_at__lte=day_end, direction=SupportMessage.DIR_INBOUND).count(),
            'messages_outbound': messages_qs.filter(created_at__gte=day_start, created_at__lte=day_end, direction=SupportMessage.DIR_OUTBOUND).count(),
            'voice_calls': calls_qs.filter(created_at__gte=day_start, created_at__lte=day_end).count(),
        })
        cursor = next_day

    summary = {
        'conversations_created': conversations.count(),
        'messages_inbound': messages_qs.filter(direction=SupportMessage.DIR_INBOUND).count(),
        'messages_outbound': messages_qs.filter(direction=SupportMessage.DIR_OUTBOUND).count(),
        'voice_calls': calls_qs.count(),
        'currently_open': SupportConversation.objects.filter(tenant=tenant, status=SupportConversation.STATUS_OPEN).count(),
        'currently_pending': SupportConversation.objects.filter(tenant=tenant, status=SupportConversation.STATUS_PENDING).count(),
    }

    detail_rows = []
    conversation_list = list(conversations.select_related('channel', 'contact', 'assigned_user').order_by('-created_at')[:250])
    for conversation in conversation_list:
        contact = conversation.contact
        contact_meta = contact.metadata_json or {}
        detail_rows.append({
            'created_at': timezone.localtime(conversation.created_at).strftime('%Y-%m-%d %H:%M'),
            'source': _infer_support_source(conversation),
            'contact_name': contact.name or '',
            'contact_phone': contact.phone_number or '',
            'contact_email': (contact_meta.get('email') or '').strip(),
            'channel_name': conversation.channel.name if conversation.channel_id else '',
            'assigned_user': conversation.assigned_user.username if conversation.assigned_user_id else '',
            'subject': conversation.subject or '',
            'status': conversation.status,
            'last_message_at': timezone.localtime(conversation.last_message_at).strftime('%Y-%m-%d %H:%M') if conversation.last_message_at else '',
            'conversation_id': conversation.id,
        })

    if (request.GET.get('format') or '').strip().lower() == 'xlsx':
        wb = Workbook()
        ws = wb.active
        ws.title = 'Support Activity'
        ws.append([
            'Date',
            'Conversations Created',
            'Open',
            'Pending',
            'Closed',
            'Inbound Messages',
            'Outbound Messages',
            'Voice Calls',
        ])
        for row in rows:
            ws.append([
                row['date'],
                row['conversations_created'],
                row['open_count'],
                row['pending_count'],
                row['closed_count'],
                row['messages_inbound'],
                row['messages_outbound'],
                row['voice_calls'],
            ])
        ws.append([])
        ws.append(['Summary'])
        for key, value in summary.items():
            ws.append([key, value])

        details = wb.create_sheet(title='Conversation Details')
        details.append([
            'Created At',
            'Source',
            'Contact Name',
            'Contact Phone',
            'Contact Email',
            'Channel',
            'Assigned User',
            'Subject',
            'Status',
            'Last Message At',
            'Conversation ID',
        ])
        for row in detail_rows:
            details.append([
                row['created_at'],
                row['source'],
                row['contact_name'],
                row['contact_phone'],
                row['contact_email'],
                row['channel_name'],
                row['assigned_user'],
                row['subject'],
                row['status'],
                row['last_message_at'],
                row['conversation_id'],
            ])
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="support-activity-{start_date.isoformat()}-to-{end_date.isoformat()}.xlsx"'
        return response

    base.update({
        'section': 'reports',
        'report_name': 'support_activity',
        'report_start': start_date.isoformat(),
        'report_end': end_date.isoformat(),
        'report_channel_id': channel_id_raw,
        'report_assigned_user_id': assigned_user_id_raw,
        'report_channels': SupportChannel.objects.filter(tenant=tenant).order_by('name'),
        'report_assigned_users': tenant.memberships.select_related('user').order_by('user__username'),
        'report_rows': rows,
        'report_summary': summary,
        'report_detail_rows': detail_rows,
    })
    return render(request, 'dashboard/report_support_activity.html', base)


@login_required
def interactions_report(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')

    today = timezone.localdate()
    start_default = today - timedelta(days=29)
    start_raw = (request.GET.get('start') or '').strip()
    end_raw = (request.GET.get('end') or '').strip()
    source_filter = (request.GET.get('source') or '').strip().lower()
    workspace_id_raw = (request.GET.get('workspace') or '').strip()
    workspace_id = int(workspace_id_raw) if workspace_id_raw.isdigit() else None

    try:
        start_date = timezone.datetime.fromisoformat(start_raw).date() if start_raw else start_default
    except ValueError:
        start_date = start_default
    try:
        end_date = timezone.datetime.fromisoformat(end_raw).date() if end_raw else today
    except ValueError:
        end_date = today

    if end_date < start_date:
        start_date, end_date = end_date, start_date

    start_dt = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
    end_dt = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))

    rows = []

    support_qs = SupportConversation.objects.select_related('channel', 'contact', 'assigned_user', 'workspace_context').filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )
    if workspace_id:
        support_qs = support_qs.filter(workspace_context_id=workspace_id)
    for conversation in support_qs[:250]:
        source = _infer_support_source(conversation)
        if source_filter and source_filter != source:
            continue
        contact_meta = conversation.contact.metadata_json or {}
        rows.append({
            'timestamp': conversation.created_at,
            'source': source,
            'end_user': conversation.contact.name or conversation.contact.phone_number or '',
            'contact_detail': (contact_meta.get('email') or '').strip() or conversation.contact.phone_number or '',
            'channel': conversation.channel.name if conversation.channel_id else '',
            'workspace': conversation.workspace_context.name if conversation.workspace_context_id else '',
            'assigned_user': conversation.assigned_user.username if conversation.assigned_user_id else '',
            'status': conversation.status,
            'preview': conversation.subject or '',
            'reference': f'support-{conversation.id}',
        })

    voice_qs = VoiceCallRecord.objects.select_related('workspace', 'support_channel').filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )
    if workspace_id:
        voice_qs = voice_qs.filter(workspace_id=workspace_id)
    for call in voice_qs[:250]:
        source = 'voice'
        if source_filter and source_filter != source:
            continue
        rows.append({
            'timestamp': call.created_at,
            'source': source,
            'end_user': call.from_number or '',
            'contact_detail': call.to_number or '',
            'channel': call.support_channel.name if call.support_channel_id else '',
            'workspace': call.workspace.name if call.workspace_id else '',
            'assigned_user': '',
            'status': call.close_reason or '',
            'preview': f'Call {call.call_sid}',
            'reference': f'voice-{call.id}',
        })

    chatbot_qs = ChatbotConversation.objects.select_related('integration', 'endpoint', 'workspace').filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )
    if workspace_id:
        chatbot_qs = chatbot_qs.filter(workspace_id=workspace_id)
    for convo in chatbot_qs[:250]:
        source = f'chatbot_{convo.platform}'
        if source_filter and source_filter != source:
            continue
        meta = convo.metadata_json or {}
        external_user = meta.get('external_user_name') or meta.get('external_user_id') or convo.external_conversation_id or ''
        channel_label = ''
        if convo.integration_id:
            channel_label = f'{convo.integration.name} ({convo.platform})'
        elif convo.platform:
            channel_label = convo.platform
        rows.append({
            'timestamp': convo.created_at,
            'source': source,
            'end_user': external_user,
            'contact_detail': convo.external_thread_id or convo.external_conversation_id or '',
            'channel': channel_label,
            'workspace': convo.workspace.name if convo.workspace_id else '',
            'assigned_user': '',
            'status': convo.status,
            'preview': convo.title or '',
            'reference': f'chatbot-{convo.id}',
        })

    rows.sort(key=lambda item: item['timestamp'], reverse=True)
    rows = rows[:500]

    summary = {
        'total_rows': len(rows),
        'support_rows': sum(1 for row in rows if row['source'] in {'support', 'sms', 'sms/voice', 'voice'} and row['reference'].startswith('support-')),
        'voice_rows': sum(1 for row in rows if row['reference'].startswith('voice-')),
        'chatbot_rows': sum(1 for row in rows if row['reference'].startswith('chatbot-')),
    }

    if (request.GET.get('format') or '').strip().lower() == 'xlsx':
        wb = Workbook()
        ws = wb.active
        ws.title = 'Interactions'
        ws.append(['Timestamp', 'Source', 'End User', 'Contact Detail', 'Channel', 'Workspace', 'Assigned User', 'Status', 'Preview', 'Reference'])
        for row in rows:
            ws.append([
                timezone.localtime(row['timestamp']).strftime('%Y-%m-%d %H:%M') if row['timestamp'] else '',
                row['source'],
                row['end_user'],
                row['contact_detail'],
                row['channel'],
                row['workspace'],
                row['assigned_user'],
                row['status'],
                row['preview'],
                row['reference'],
            ])
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="interactions-{start_date.isoformat()}-to-{end_date.isoformat()}.xlsx"'
        return response

    base.update({
        'section': 'reports',
        'report_name': 'interactions',
        'report_start': start_date.isoformat(),
        'report_end': end_date.isoformat(),
        'report_source': source_filter,
        'report_workspace_id': workspace_id_raw,
        'report_source_choices': [
            ('', 'All sources'),
            ('support', 'Support'),
            ('sms', 'SMS'),
            ('sms/voice', 'SMS/Voice'),
            ('voice', 'Voice'),
            (f'chatbot_{ChatbotIntegration.PLATFORM_TELEGRAM}', 'Chatbot · Telegram'),
            (f'chatbot_{ChatbotIntegration.PLATFORM_DISCORD}', 'Chatbot · Discord'),
        ],
        'report_workspaces': tenant.workspaces.order_by('name'),
        'report_rows': rows,
        'report_summary': summary,
    })
    return render(request, 'dashboard/report_interactions.html', base)
