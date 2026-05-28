from django.db import models


class Tenant(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Workspace(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='workspaces')
    name = models.CharField(max_length=200)
    slug = models.SlugField()
    default_embedding_model = models.CharField(max_length=200, default='text-embedding-3-large')
    default_chunk_size = models.PositiveIntegerField(default=800)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'name']
        unique_together = [('tenant', 'slug')]

    def __str__(self):
        return f'{self.tenant.slug}/{self.slug}'


class APIKey(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='api_keys')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='api_keys', null=True, blank=True)
    label = models.CharField(max_length=200)
    key_prefix = models.CharField(max_length=24)
    key_hash = models.CharField(max_length=255)
    scopes_json = models.JSONField(default=list, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tenant__name', 'label']

    def __str__(self):
        return f'{self.label} ({self.key_prefix})'
