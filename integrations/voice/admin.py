from django.contrib import admin

from .models import VoiceCallRecord


@admin.register(VoiceCallRecord)
class VoiceCallRecordAdmin(admin.ModelAdmin):
    list_display = ('call_sid', 'tenant', 'support_channel', 'from_number', 'to_number', 'started_at', 'close_reason', 'turn_count')
    search_fields = ('call_sid', 'from_number', 'to_number')
    list_filter = ('tenant', 'support_channel', 'close_reason', 'created_at')
