from django.db.models import Q
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Chunk
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

        qs = Chunk.objects.filter(tenant=tenant, workspace=workspace)
        if query:
            for token in [part.strip() for part in query.split() if part.strip()][:5]:
                qs = qs.filter(Q(text__icontains=token))
        results = list(qs.select_related('document')[:top_k])

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
                }
                for row in results
            ]
        })
