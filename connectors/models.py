from django.db import models

from control.models import Tenant, Workspace


class Connector(models.Model):
    PROVIDER_SHAREPOINT = 'sharepoint'
    PROVIDER_GOOGLE_DRIVE = 'google_drive'
    PROVIDER_CHOICES = [
        (PROVIDER_SHAREPOINT, 'SharePoint'),
        (PROVIDER_GOOGLE_DRIVE, 'Google Drive'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='connectors')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='connectors')
    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES)
    label = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    config_json = models.JSONField(default=dict, blank=True)
    sync_enabled = models.BooleanField(default=False)
    sync_frequency_minutes = models.PositiveIntegerField(default=60)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'workspace__name', 'label']

    def __str__(self):
        return f'{self.label} ({self.provider})'


class ConnectorSyncRun(models.Model):
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
    ]

    connector = models.ForeignKey(Connector, on_delete=models.CASCADE, related_name='sync_runs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    summary_json = models.JSONField(default=dict, blank=True)
    error_text = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'Sync {self.id} for {self.connector}'


class ExternalDocumentBinding(models.Model):
    connector = models.ForeignKey(Connector, on_delete=models.CASCADE, related_name='bindings')
    external_id = models.CharField(max_length=255)
    external_path = models.CharField(max_length=1000, blank=True, default='')
    etag = models.CharField(max_length=255, blank=True, default='')
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, related_name='external_bindings')
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('connector', 'external_id')]
        ordering = ['connector_id', 'external_path']

    def __str__(self):
        return f'{self.connector} :: {self.external_path or self.external_id}'
