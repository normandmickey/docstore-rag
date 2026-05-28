from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from control.models import Tenant, Workspace
from ingestion.models import IngestionJob
from ingestion.tasks import ingest_document_task
from .models import Document, DocumentVersion


class DocumentCreateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField()
    workspace_id = serializers.IntegerField()
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
    def post(self, request):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = Tenant.objects.get(id=data['tenant_id'])
        workspace = Workspace.objects.get(id=data['workspace_id'], tenant=tenant)
        uploaded_file = data.get('file')
        filename = data.get('filename') or (uploaded_file.name if uploaded_file else 'untitled.txt')
        object_key = data.get('object_key') or f'{tenant.slug}/{workspace.slug}/{filename}'
        size_bytes = data.get('size_bytes') or (uploaded_file.size if uploaded_file else 0)

        document = Document.objects.create(
            tenant=tenant,
            workspace=workspace,
            collection=data.get('collection', ''),
            filename=filename,
            mime_type=data.get('mime_type') or getattr(uploaded_file, 'content_type', '') or '',
            size_bytes=size_bytes,
            object_key=object_key,
            content_hash=data.get('content_hash', ''),
            source_type=data.get('source_type', Document.SOURCE_UPLOAD),
            source_url=data.get('source_url', ''),
            uploaded_by=request.user if request.user.is_authenticated else None,
            file=uploaded_file,
        )
        version = DocumentVersion.objects.create(
            document=document,
            version_number=1,
            object_key=document.object_key,
            content_hash=document.content_hash,
            extraction_metadata_json={'raw_text': data.get('raw_text', '')},
        )
        job = IngestionJob.objects.create(
            tenant=tenant,
            workspace=workspace,
            document=document,
            document_version=version,
            status=IngestionJob.STATUS_QUEUED,
            stage='queued',
        )
        ingest_document_task.delay(job.id)
        return Response(
            {
                'document_id': document.id,
                'document_version_id': version.id,
                'ingestion_job_id': job.id,
                'status': document.status,
            },
            status=status.HTTP_201_CREATED,
        )
