from django.db import models

from control.models import Tenant, Workspace
from documents.models import Document, DocumentVersion


class IngestionJob(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ingestion_jobs')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='ingestion_jobs')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='ingestion_jobs')
    document_version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name='ingestion_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    stage = models.CharField(max_length=120, blank=True, default='queued')
    error_text = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'workspace', 'status']),
        ]

    def __str__(self):
        return f'Job {self.id} for {self.document.filename}'
