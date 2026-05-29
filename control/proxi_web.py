from django.conf import settings
from django.db import models

from .models import Tenant, Workspace


class ProxiWebThread(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='proxi_web_threads')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='proxi_web_threads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proxi_web_threads')
    title = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['tenant', 'workspace', 'user']),
        ]

    def __str__(self):
        return self.title or f'Proxi-Web thread {self.id}'


class ProxiWebMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_USER, 'User'),
        (ROLE_ASSISTANT, 'Assistant'),
    ]

    thread = models.ForeignKey(ProxiWebThread, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    retrieval_metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['thread', 'id']),
        ]

    def __str__(self):
        return f'{self.thread_id}::{self.role}::{self.id}'
