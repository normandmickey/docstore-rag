from django.db import models

from control.models import Tenant, Workspace


class RetrievalLog(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='retrieval_logs')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='retrieval_logs')
    query_text = models.TextField()
    top_k = models.PositiveIntegerField(default=5)
    result_count = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'workspace', 'created_at']),
        ]

    def __str__(self):
        return f'Retrieval {self.id} ({self.workspace})'
