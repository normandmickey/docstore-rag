from django.contrib import admin
from django.utils.html import format_html

from .models import VoiceCallRecord


@admin.register(VoiceCallRecord)
class VoiceCallRecordAdmin(admin.ModelAdmin):
    list_display = (
        'call_sid',
        'tenant',
        'workspace',
        'support_channel',
        'from_number',
        'to_number',
        'started_at',
        'ended_at',
        'close_reason',
        'turn_count',
        'transcript_turns',
    )
    search_fields = ('call_sid', 'stream_sid', 'from_number', 'to_number')
    list_filter = ('tenant', 'workspace', 'support_channel', 'close_reason', 'source_label', 'created_at')
    readonly_fields = (
        'call_sid',
        'stream_sid',
        'tenant',
        'workspace',
        'support_channel',
        'from_number',
        'to_number',
        'started_at',
        'ended_at',
        'close_reason',
        'turn_count',
        'source_label',
        'created_at',
        'updated_at',
        'transcript_preview',
        'metadata_preview',
    )
    fields = (
        'call_sid',
        'stream_sid',
        'tenant',
        'workspace',
        'support_channel',
        'from_number',
        'to_number',
        ('started_at', 'ended_at'),
        ('close_reason', 'turn_count', 'source_label'),
        ('created_at', 'updated_at'),
        'transcript_preview',
        'metadata_preview',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def transcript_turns(self, obj):
        return len(obj.transcript_json or [])

    transcript_turns.short_description = 'Turns'

    def transcript_preview(self, obj):
        items = obj.transcript_json or []
        if not items:
            return 'No transcript stored.'
        lines = []
        for turn in items[:20]:
            role = (turn or {}).get('role') or 'unknown'
            text = (turn or {}).get('text') or ''
            lines.append(f'{role}: {text}'.strip())
        if len(items) > 20:
            lines.append(f'… {len(items) - 20} more turns')
        return format_html('<pre style="max-height: 28rem; overflow:auto;">{}</pre>', '\n'.join(lines))

    transcript_preview.short_description = 'Transcript'

    def metadata_preview(self, obj):
        import json
        return format_html('<pre style="max-height: 20rem; overflow:auto;">{}</pre>', json.dumps(obj.metadata_json or {}, indent=2, sort_keys=True))

    metadata_preview.short_description = 'Metadata'
