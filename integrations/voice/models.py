from django.db import models

from control.models import Tenant, Workspace
from support.models import SupportChannel


class VoiceCallRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='voice_call_records')
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_call_records')
    support_channel = models.ForeignKey(SupportChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_call_records')
    call_sid = models.CharField(max_length=128, unique=True)
    stream_sid = models.CharField(max_length=128, blank=True)
    from_number = models.CharField(max_length=64, blank=True)
    to_number = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=128, blank=True)
    turn_count = models.PositiveIntegerField(default=0)
    source_label = models.CharField(max_length=64, default='docstore-voice-agent')
    transcript_json = models.JSONField(default=list, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.call_sid} ({self.from_number} -> {self.to_number})'
