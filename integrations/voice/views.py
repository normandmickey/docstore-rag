import json
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from api.auth import get_api_key_from_header
from support.models import SupportChannel
from control.models import Tenant, Workspace

from .models import VoiceCallRecord


def _dt(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    return parsed


@csrf_exempt
def ingest_voice_call(request):
    if not getattr(settings, 'VOICE_INTEGRATION_ENABLED', False):
        return JsonResponse({'ok': False, 'error': 'voice_integration_disabled'}, status=404)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'method_not_allowed'}, status=405)

    api_key = get_api_key_from_header(request)
    if not api_key:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

    call_sid = (payload.get('call_sid') or '').strip()
    if not call_sid:
        return JsonResponse({'ok': False, 'error': 'call_sid_required'}, status=400)

    tenant = None
    tenant_id = payload.get('tenant_id')
    if tenant_id:
        tenant = Tenant.objects.filter(id=tenant_id).first()
    workspace = Workspace.objects.filter(id=payload.get('workspace_id')).first() if payload.get('workspace_id') else None
    support_channel = SupportChannel.objects.filter(id=payload.get('support_channel_id')).first() if payload.get('support_channel_id') else None

    record, created = VoiceCallRecord.objects.update_or_create(
        call_sid=call_sid,
        defaults={
            'tenant': tenant or getattr(support_channel, 'tenant', None) or getattr(workspace, 'tenant', None),
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
    if not record.tenant:
        return JsonResponse({'ok': False, 'error': 'tenant_required'}, status=400)
    return JsonResponse({'ok': True, 'call_sid': record.call_sid, 'created': created})
