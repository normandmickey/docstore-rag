from django.contrib import admin, messages

from ingestion.models import IngestionJob
from .models import Chunk, Document, DocumentVersion


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ('created_at',)


def queue_ingestion(modeladmin, request, queryset):
    queued = 0
    for document in queryset:
        version = document.versions.order_by('-version_number', '-id').first()
        if not version:
            continue
        IngestionJob.objects.create(
            tenant=document.tenant,
            workspace=document.workspace,
            document=document,
            document_version=version,
            status=IngestionJob.STATUS_QUEUED,
            stage='queued',
        )
        document.status = Document.STATUS_PENDING
        document.save(update_fields=['status', 'updated_at'])
        queued += 1
    modeladmin.message_user(request, f'Queued ingestion for {queued} document(s).', level=messages.SUCCESS)


queue_ingestion.short_description = 'Queue ingestion for selected documents'


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'tenant', 'workspace', 'collection', 'status', 'mime_type', 'size_bytes', 'created_at')
    search_fields = ('filename', 'object_key', 'content_hash', 'workspace__name', 'tenant__name')
    list_filter = ('tenant', 'workspace', 'status', 'source_type')
    inlines = [DocumentVersionInline]
    actions = [queue_ingestion]


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'version_number', 'parse_status', 'created_at')
    search_fields = ('document__filename', 'object_key', 'content_hash')
    list_filter = ('parse_status',)


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'chunk_index', 'token_count', 'created_at')
    search_fields = ('document__filename', 'text')
    list_filter = ('tenant', 'workspace')
