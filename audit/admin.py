from django.contrib import admin

from .models import RetrievalLog


@admin.register(RetrievalLog)
class RetrievalLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'tenant', 'workspace', 'top_k', 'result_count', 'latency_ms', 'created_at')
    search_fields = ('query_text', 'workspace__name', 'tenant__name')
    list_filter = ('tenant', 'workspace')
