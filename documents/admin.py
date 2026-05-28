from django.contrib import admin

from .models import Chunk, Document, DocumentVersion


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'tenant', 'workspace', 'collection', 'status', 'mime_type', 'size_bytes', 'created_at')
    search_fields = ('filename', 'object_key', 'content_hash', 'workspace__name', 'tenant__name')
    list_filter = ('tenant', 'workspace', 'status', 'source_type')
    inlines = [DocumentVersionInline]


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
