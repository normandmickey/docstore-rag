from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from control.models import Tenant, Workspace
from .storage import DocumentStorage


document_storage = DocumentStorage()


class Document(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_DELETED = 'deleted'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DELETED, 'Deleted'),
    ]

    SOURCE_UPLOAD = 'upload'
    SOURCE_URL = 'url'
    SOURCE_CONNECTOR = 'connector'
    SOURCE_CHOICES = [
        (SOURCE_UPLOAD, 'Upload'),
        (SOURCE_URL, 'URL'),
        (SOURCE_CONNECTOR, 'Connector'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='documents')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='documents')
    collection = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True, default='')
    size_bytes = models.BigIntegerField(default=0)
    object_key = models.CharField(max_length=500)
    content_hash = models.CharField(max_length=128, blank=True, default='')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    source_url = models.URLField(blank=True, default='')
    file = models.FileField(upload_to='documents/%Y/%m/%d/', storage=document_storage, blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'workspace', 'status']),
            models.Index(fields=['tenant', 'workspace', 'collection']),
        ]

    def soft_delete(self):
        self.status = self.STATUS_DELETED
        self.save(update_fields=['status', 'updated_at'])

    def restore(self):
        self.status = self.STATUS_READY if self.versions.exists() else self.STATUS_PENDING
        self.save(update_fields=['status', 'updated_at'])

    def __str__(self):
        return f'{self.filename} [{self.workspace}]'


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    object_key = models.CharField(max_length=500)
    content_hash = models.CharField(max_length=128, blank=True, default='')
    parse_status = models.CharField(max_length=20, default='pending')
    extraction_metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('document', 'version_number')]

    def __str__(self):
        return f'{self.document.filename} v{self.version_number}'


class Chunk(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='chunks')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='chunks')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    document_version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    metadata_json = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=3072, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_id', 'chunk_index']
        unique_together = [('document_version', 'chunk_index')]
        indexes = [
            models.Index(fields=['tenant', 'workspace', 'document']),
        ]

    def __str__(self):
        return f'Chunk {self.chunk_index} of {self.document.filename}'
