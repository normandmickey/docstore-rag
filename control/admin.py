from django.contrib import admin

from .models import APIKey, ExternalAccount, InviteToken, Tenant, TenantMembership, Workspace


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'status', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('status',)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'slug', 'default_embedding_model', 'default_chunk_size')
    search_fields = ('name', 'slug', 'tenant__name')
    list_filter = ('tenant',)


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'user', 'role', 'created_at')
    search_fields = ('tenant__name', 'user__username', 'user__email')
    list_filter = ('role', 'tenant')


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('label', 'tenant', 'workspace', 'key_prefix', 'active', 'last_used_at')
    search_fields = ('label', 'key_prefix', 'tenant__name', 'workspace__name')
    list_filter = ('tenant', 'active')


@admin.register(ExternalAccount)
class ExternalAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'email', 'display_name', 'tenant', 'workspace', 'expires_at')
    search_fields = ('user__username', 'email', 'display_name', 'external_user_id')
    list_filter = ('provider', 'tenant')


@admin.register(InviteToken)
class InviteTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'tenant', 'workspace', 'role', 'active', 'created_by', 'claimed_by', 'expires_at', 'created_at')
    search_fields = ('email', 'token', 'tenant__name', 'workspace__name', 'created_by__username', 'claimed_by__username')
    list_filter = ('active', 'role', 'tenant')
