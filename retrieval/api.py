from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from control.api_guard import resolve_request_context
from .service import answer_question, retrieve_chunks


def _preferred_source_url(row):
    document = row.document
    if document.source_url:
        return document.source_url

    chunk_meta = getattr(row, 'metadata_json', {}) or {}
    for key in ('webViewLink', 'web_url', 'source_url', 'url'):
        value = chunk_meta.get(key)
        if value:
            return value

    try:
        latest_version = document.versions.first()
        version_meta = (latest_version.extraction_metadata_json or {}) if latest_version else {}
    except Exception:
        version_meta = {}
    for key in ('webViewLink', 'web_url', 'source_url', 'url'):
        value = version_meta.get(key)
        if value:
            return value

    return f'/documents/{document.id}/download/'


def _serialize_source(row):
    return {
        'chunk_id': row.id,
        'document_id': row.document_id,
        'document': row.document.filename,
        'chunk_index': row.chunk_index,
        'text': row.text,
        'distance': float(getattr(row, 'distance', 0.0)),
        'source_url': _preferred_source_url(row),
        'source_url_kind': 'external' if _preferred_source_url(row).startswith('http') else 'docstore',
    }


class SearchSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    query = serializers.CharField()
    top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=50)


class ChatSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    question = serializers.CharField()
    top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=20)
    document_id = serializers.IntegerField(required=False)


class SearchView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = SearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        query = data['query'].strip()
        top_k = data['top_k']

        results = retrieve_chunks(
            tenant=tenant,
            workspace=workspace,
            query=query,
            top_k=top_k,
        )

        return Response({
            'results': [_serialize_source(row) for row in results]
        })


class ChatView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )

        answer, results = answer_question(
            tenant=tenant,
            workspace=workspace,
            query=data['question'].strip(),
            top_k=data['top_k'],
            document_id=data.get('document_id'),
        )

        return Response({
            'answer': answer,
            'sources': [_serialize_source(row) for row in results]
        })
