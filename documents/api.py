from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from control.api_guard import resolve_request_context
from control.models import Workspace
from .models import Document
from .upload_service import collect_urls_for_ingest, create_or_reuse_document, create_or_reuse_url_document


class DocumentCreateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    additional_workspace_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    filename = serializers.CharField(max_length=255, required=False)
    mime_type = serializers.CharField(max_length=120, required=False, allow_blank=True)
    size_bytes = serializers.IntegerField(required=False, default=0)
    object_key = serializers.CharField(max_length=500, required=False, allow_blank=True)
    content_hash = serializers.CharField(max_length=128, required=False, allow_blank=True)
    collection = serializers.CharField(max_length=120, required=False, allow_blank=True)
    source_type = serializers.ChoiceField(choices=Document.SOURCE_CHOICES, required=False, default=Document.SOURCE_UPLOAD)
    source_url = serializers.URLField(required=False, allow_blank=True)
    file = serializers.FileField(required=False)
    raw_text = serializers.CharField(required=False, allow_blank=True)


class DocumentCreateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Create or upload a document',
        description='Upload a document into Docstore and optionally assign it to multiple workspaces at ingest time without duplicating the file, versions, chunks, or embeddings.',
        request=DocumentCreateSerializer,
        responses={
            201: OpenApiResponse(description='Document created or versioned successfully.'),
            200: OpenApiResponse(description='Existing duplicate detected; existing document returned logically.'),
        },
        examples=[
            OpenApiExample(
                'Multi-workspace document ingest',
                value={
                    'tenant_id': 2,
                    'workspace_id': 3,
                    'additional_workspace_ids': [4, 5],
                    'filename': 'employee-handbook.pdf',
                    'collection': 'hr',
                    'source_type': 'upload',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Create response',
                value={
                    'document_id': 123,
                    'document_version_id': 456,
                    'ingestion_job_id': 789,
                    'status': 'pending',
                    'mode': 'created',
                    'assigned_workspace_ids': [3, 4, 5],
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        uploaded_file = data.get('file')
        filename = data.get('filename') or (uploaded_file.name if uploaded_file else 'untitled.txt')
        size_bytes = data.get('size_bytes') or (uploaded_file.size if uploaded_file else 0)
        additional_workspaces = list(Workspace.objects.filter(
            tenant=tenant,
            id__in=data.get('additional_workspace_ids') or [],
        ))

        result = create_or_reuse_document(
            tenant=tenant,
            workspace=workspace,
            uploaded_file=uploaded_file,
            filename=filename,
            mime_type=data.get('mime_type') or getattr(uploaded_file, 'content_type', '') or '',
            size_bytes=size_bytes,
            collection=data.get('collection', ''),
            uploaded_by=request.user if request.user.is_authenticated else None,
            raw_text=data.get('raw_text', ''),
            source_type=data.get('source_type', Document.SOURCE_UPLOAD),
            source_url=data.get('source_url', ''),
            additional_workspaces=additional_workspaces,
        )
        document = result['document']
        version = result['version']
        job = result['job']
        return Response(
            {
                'document_id': document.id,
                'document_version_id': version.id if version else None,
                'ingestion_job_id': job.id if job else None,
                'status': document.status,
                'mode': result['mode'],
                'assigned_workspace_ids': list(document.workspace_assignments.values_list('workspace_id', flat=True)),
            },
            status=status.HTTP_201_CREATED if result['mode'] != 'duplicate' else status.HTTP_200_OK,
        )


class URLIngestSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    additional_workspace_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    urls = serializers.ListField(child=serializers.URLField(), allow_empty=False)
    collection = serializers.CharField(max_length=120, required=False, allow_blank=True)
    crawl_mode = serializers.ChoiceField(choices=['single', 'same_domain'], required=False, default='single')
    max_pages = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)


class URLIngestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Ingest one or more URLs',
        description='Fetch one or more URLs, extract content, create/reuse documents, and optionally assign them to multiple workspaces at ingest time.',
        request=URLIngestSerializer,
        responses={200: OpenApiResponse(description='URL ingest completed.')},
        examples=[
            OpenApiExample(
                'URL ingest with additional workspaces',
                value={
                    'tenant_id': 2,
                    'workspace_id': 3,
                    'additional_workspace_ids': [4, 5],
                    'urls': ['https://example.com/handbook'],
                    'collection': 'hr',
                    'crawl_mode': 'single',
                    'max_pages': 10,
                },
                request_only=True,
            ),
            OpenApiExample(
                'URL ingest response',
                value={
                    'created': 1,
                    'versioned': 0,
                    'skipped': 0,
                    'failed': [],
                    'ingested': [
                        {
                            'url': 'https://example.com/handbook',
                            'document_id': 123,
                            'mode': 'created',
                            'assigned_workspace_ids': [3, 4, 5],
                        }
                    ],
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = URLIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        urls = collect_urls_for_ingest(data['urls'], crawl_mode=data['crawl_mode'], max_pages=data['max_pages'])
        additional_workspaces = list(Workspace.objects.filter(
            tenant=tenant,
            id__in=data.get('additional_workspace_ids') or [],
        ))

        created = 0
        versioned = 0
        skipped = 0
        failed = []
        ingested = []

        for url in urls:
            try:
                result = create_or_reuse_url_document(
                    tenant=tenant,
                    workspace=workspace,
                    url=url,
                    collection=data.get('collection', ''),
                    uploaded_by=request.user if request.user.is_authenticated else None,
                    additional_workspaces=additional_workspaces,
                )
                ingested.append({
                    'url': result.get('normalized_url', url),
                    'document_id': result['document'].id,
                    'mode': result['mode'],
                    'assigned_workspace_ids': list(result['document'].workspace_assignments.values_list('workspace_id', flat=True)),
                })
                if result['mode'] == 'duplicate':
                    skipped += 1
                elif result['mode'] == 'versioned':
                    versioned += 1
                else:
                    created += 1
            except Exception as exc:
                failed.append({'url': url, 'error': str(exc)})

        return Response({
            'created': created,
            'versioned': versioned,
            'skipped': skipped,
            'failed': failed,
            'ingested': ingested,
        })


class DocumentDeleteSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    document_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class DocumentDeleteView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = DocumentDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        documents = list(Document.objects.filter(
            id__in=data['document_ids'],
            tenant=tenant,
            workspace_assignments__workspace=workspace,
        ).exclude(status=Document.STATUS_DELETED).distinct())

        for document in documents:
            document.soft_delete()

        return Response({
            'soft_deleted': len(documents),
            'document_ids': [doc.id for doc in documents],
        })


class DocumentRestoreView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = DocumentDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        documents = list(Document.objects.filter(
            id__in=data['document_ids'],
            tenant=tenant,
            workspace_assignments__workspace=workspace,
            status=Document.STATUS_DELETED,
        ).distinct())

        for document in documents:
            document.restore()

        return Response({
            'restored': len(documents),
            'document_ids': [doc.id for doc in documents],
        })


class DocumentPurgeView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = DocumentDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        documents = list(Document.objects.filter(
            id__in=data['document_ids'],
            tenant=tenant,
            workspace_assignments__workspace=workspace,
            status=Document.STATUS_DELETED,
        ).distinct())

        purged_ids = []
        for document in documents:
            if document.file:
                document.file.delete(save=False)
            purged_ids.append(document.id)
            document.delete()

        return Response({
            'purged': len(purged_ids),
            'document_ids': purged_ids,
        })
