from django.contrib import admin

from .models import IngestionJob


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'tenant', 'workspace', 'status', 'stage', 'created_at', 'finished_at')
    search_fields = ('document__filename', 'error_text')
    list_filter = ('tenant', 'workspace', 'status', 'stage')
