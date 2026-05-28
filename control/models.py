from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


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
    default_chunk_size = models.PositiveIntegerField(default=400)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant__name', 'name']
        unique_together = [('tenant', 'slug')]

    def __str__(self):
        return f'{self.tenant.slug}/{self.slug}'


class TenantMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('tenant', 'user')]
        ordering = ['tenant__name', 'user__username']

    def __str__(self):
        return f'{self.user} @ {self.tenant} ({self.role})'


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


class ExternalAccount(models.Model):
    PROVIDER_MICROSOFT = 'microsoft'
    PROVIDER_CHOICES = [
        (PROVIDER_MICROSOFT, 'Microsoft'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='external_accounts')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='external_accounts')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='external_accounts', null=True, blank=True)
    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES)
    external_user_id = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    display_name = models.CharField(max_length=255, blank=True, default='')
    access_token = models.TextField(blank=True, default='')
    refresh_token = models.TextField(blank=True, default='')
    expires_at = models.DateTimeField(null=True, blank=True)
    scopes_json = models.JSONField(default=list, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username', 'provider', 'created_at']
        unique_together = [('user', 'provider', 'external_user_id')]

    def __str__(self):
        return f'{self.user} :: {self.provider} :: {self.email or self.external_user_id or "connected"}'


class InviteToken(models.Model):
    ROLE_OWNER = TenantMembership.ROLE_OWNER
    ROLE_ADMIN = TenantMembership.ROLE_ADMIN
    ROLE_MEMBER = TenantMembership.ROLE_MEMBER
    ROLE_CHOICES = TenantMembership.ROLE_CHOICES

    email = models.EmailField(blank=True, default='')
    token = models.CharField(max_length=128, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='invite_tokens', null=True, blank=True)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invite_tokens', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    note = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_invite_tokens')
    claimed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='claimed_invite_tokens')
    claimed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email or self.token[:12]
