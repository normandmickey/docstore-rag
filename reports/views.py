from datetime import timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from openpyxl import Workbook

from control.views import _dashboard_base, _handle_workspace_actions
from support.models import SupportConversation, SupportMessage
from integrations.voice.models import VoiceCallRecord


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

    conversations = SupportConversation.objects.filter(tenant=tenant, created_at__gte=start_dt, created_at__lte=end_dt)
    messages_qs = SupportMessage.objects.filter(conversation__tenant=tenant, created_at__gte=start_dt, created_at__lte=end_dt)
    calls_qs = VoiceCallRecord.objects.filter(tenant=tenant, created_at__gte=start_dt, created_at__lte=end_dt)

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
        'report_rows': rows,
        'report_summary': summary,
    })
    return render(request, 'dashboard/report_support_activity.html', base)
