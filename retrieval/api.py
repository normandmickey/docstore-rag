from pgvector.django import CosineDistance
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Chunk
from providers import embed_texts
from audit.models import RetrievalLog
from control.models import Tenant, Workspace


class SearchSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField()
    workspace_id = serializers.IntegerField()
    query = serializers.CharField()
    top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=50)


class SearchView(APIView):
    def post(self, request):
        serializer = SearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = Tenant.objects.get(id=data['tenant_id'])
        workspace = Workspace.objects.get(id=data['workspace_id'], tenant=tenant)
        query = data['query'].strip()
        top_k = data['top_k']

        query_vector = embed_texts([query])[0]
        results = list(
            Chunk.objects.filter(tenant=tenant, workspace=workspace, embedding__isnull=False)
            .select_related('document')
            .annotate(distance=CosineDistance('embedding', query_vector))
            .order_by('distance')[:top_k]
        )

        RetrievalLog.objects.create(
            tenant=tenant,
            workspace=workspace,
            query_text=query,
            top_k=top_k,
            result_count=len(results),
            latency_ms=0,
            metadata_json={'mode': 'keyword_stub'},
        )

        return Response({
            'results': [
                {
                    'chunk_id': row.id,
                    'document_id': row.document_id,
                    'document': row.document.filename,
                    'chunk_index': row.chunk_index,
                    'text': row.text,
                    'distance': float(getattr(row, 'distance', 0.0)),
                }
                for row in results
            ]
        })
