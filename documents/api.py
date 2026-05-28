from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from control.models import Tenant, Workspace
from .upload_service import create_or_reuse_document


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
        size_bytes = data.get('size_bytes') or (uploaded_file.size if uploaded_file else 0)

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
            },
            status=status.HTTP_201_CREATED if result['mode'] != 'duplicate' else status.HTTP_200_OK,
        )
