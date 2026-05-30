import json

from django.conf import settings
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import PermissionDenied

from control.api_guard import resolve_request_context
from control.models import Workspace
from support.models import SupportChannel

from .models import VoiceCallRecord


def _dt(value):
    if not value:
        return None
    return parse_datetime(value)


@csrf_exempt
def ingest_voice_call(request):
    if not getattr(settings, 'VOICE_INTEGRATION_ENABLED', False):
        return JsonResponse({'ok': False, 'error': 'voice_integration_disabled'}, status=404)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'method_not_allowed'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

    call_sid = (payload.get('call_sid') or '').strip()
    if not call_sid:
        return JsonResponse({'ok': False, 'error': 'call_sid_required'}, status=400)

    try:
        tenant, workspace_ctx, _api_key = resolve_request_context(
            request,
            tenant_id=payload.get('tenant_id'),
            workspace_id=payload.get('workspace_id'),
        )
    except PermissionDenied as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=403)

    workspace = workspace_ctx or (Workspace.objects.filter(id=payload.get('workspace_id')).first() if payload.get('workspace_id') else None)
    support_channel = SupportChannel.objects.filter(id=payload.get('support_channel_id')).first() if payload.get('support_channel_id') else None
    tenant = tenant or getattr(support_channel, 'tenant', None) or getattr(workspace, 'tenant', None)
    if not tenant:
        return JsonResponse({'ok': False, 'error': 'tenant_required'}, status=400)

    record, created = VoiceCallRecord.objects.update_or_create(
        call_sid=call_sid,
        defaults={
            'tenant': tenant,
            'workspace': workspace,
            'support_channel': support_channel,
            'stream_sid': payload.get('stream_sid', ''),
            'from_number': payload.get('from_number', ''),
            'to_number': payload.get('to_number', ''),
            'started_at': _dt(payload.get('started_at')),
            'ended_at': _dt(payload.get('ended_at')),
            'close_reason': payload.get('close_reason', ''),
            'turn_count': payload.get('turn_count') or 0,
            'source_label': payload.get('source', 'docstore-voice-agent'),
            'transcript_json': payload.get('transcript') or [],
            'metadata_json': payload.get('metadata') or {},
        },
    )
    return JsonResponse({'ok': True, 'call_sid': record.call_sid, 'created': created})
