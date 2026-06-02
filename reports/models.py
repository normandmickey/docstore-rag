from django.conf import settings
from django.db import models

from control.models import Tenant, Workspace


class SpreadsheetTransformTemplate(models.Model):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_WORKSPACE = 'workspace'
    VISIBILITY_TENANT = 'tenant'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_WORKSPACE, 'Workspace'),
        (VISIBILITY_TENANT, 'Tenant'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='spreadsheet_transform_templates')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='spreadsheet_transform_templates')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spreadsheet_transform_templates')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    source_headers_json = models.JSONField(default=list, blank=True)
    output_plan_json = models.JSONField(default=list, blank=True)
    column_plan_json = models.JSONField(default=list, blank=True)
    transform_request = models.TextField(blank=True, default='')
    export_format = models.CharField(max_length=10, choices=SpreadsheetTransformJob.EXPORT_CHOICES if 'SpreadsheetTransformJob' in globals() else [('xlsx', 'XLSX'), ('csv', 'CSV')], default='xlsx')
    strict_sanitization = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'workspace', 'visibility']),
        ]

    def __str__(self):
        return self.name


class SpreadsheetTransformJob(models.Model):
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

    EXPORT_XLSX = 'xlsx'
    EXPORT_CSV = 'csv'
    EXPORT_CHOICES = [
        (EXPORT_XLSX, 'XLSX'),
        (EXPORT_CSV, 'CSV'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='spreadsheet_transform_jobs')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='spreadsheet_transform_jobs')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spreadsheet_transform_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    export_format = models.CharField(max_length=10, choices=EXPORT_CHOICES, default=EXPORT_XLSX)
    source_name = models.CharField(max_length=255, blank=True, default='')
    transform_request = models.TextField(blank=True, default='')
    strict_sanitization = models.BooleanField(default=False)
    plan_json = models.JSONField(default=dict, blank=True)
    headers_json = models.JSONField(default=list, blank=True)
    rows_json = models.JSONField(default=list, blank=True)
    output_file = models.FileField(upload_to='reports/spreadsheet_transforms/%Y/%m/%d/', blank=True, null=True)
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
        return f'SpreadsheetTransformJob {self.id} ({self.status})'
