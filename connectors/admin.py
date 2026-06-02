from django.contrib import admin

from .models import Connector, ConnectorSyncRun, ExternalDocumentBinding, TenantShippingIntegration


@admin.register(Connector)
class ConnectorAdmin(admin.ModelAdmin):
    list_display = ('label', 'provider', 'tenant', 'workspace', 'status', 'last_synced_at')
    search_fields = ('label', 'tenant__name', 'workspace__name')
    list_filter = ('provider', 'status', 'tenant')


@admin.register(ConnectorSyncRun)
class ConnectorSyncRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'connector', 'status', 'started_at', 'finished_at')
    search_fields = ('connector__label', 'connector__tenant__name', 'connector__workspace__name')
    list_filter = ('status', 'connector__provider')


@admin.register(ExternalDocumentBinding)
class ExternalDocumentBindingAdmin(admin.ModelAdmin):
    list_display = ('connector', 'external_id', 'external_path', 'document', 'etag', 'updated_at')
    search_fields = ('external_id', 'external_path', 'document__filename', 'connector__label')
    list_filter = ('connector',)


@admin.register(TenantShippingIntegration)
class TenantShippingIntegrationAdmin(admin.ModelAdmin):
    list_display = ('label', 'provider', 'tenant', 'status', 'base_url', 'last_tested_at', 'last_test_status')
    search_fields = ('label', 'tenant__name', 'base_url')
    list_filter = ('provider', 'status', 'tenant')
