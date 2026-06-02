from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from control.api_guard import resolve_request_context
from .service import answer_question, retrieve_chunks, shipping_answer_payload


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
    temperature = serializers.FloatField(required=False, min_value=0, max_value=2)


class SearchView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Search document chunks',
        description='Run retrieval against the current tenant/workspace and return the most relevant document chunks with preferred source URLs.',
        request=SearchSerializer,
        responses={200: OpenApiResponse(description='Search results returned successfully.')},
        examples=[
            OpenApiExample(
                'Search request',
                value={
                    'tenant_id': 2,
                    'workspace_id': 3,
                    'query': 'How do I update direct deposit?',
                    'top_k': 5,
                },
                request_only=True,
            ),
            OpenApiExample(
                'Search response',
                value={
                    'results': [
                        {
                            'chunk_id': 11,
                            'document_id': 123,
                            'document': 'Employee Handbook.pdf',
                            'chunk_index': 4,
                            'text': 'To update direct deposit, log into the employee portal...',
                            'distance': 0.11,
                            'source_url': 'https://drive.google.com/file/d/.../view',
                            'source_url_kind': 'external',
                        }
                    ]
                },
                response_only=True,
            ),
        ],
    )
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

    @extend_schema(
        summary='Ask a question against workspace documents',
        description='Return a grounded answer plus supporting sources from the current tenant/workspace. Sources now prefer original external URLs when available.',
        request=ChatSerializer,
        responses={200: OpenApiResponse(description='Grounded answer returned successfully.')},
        examples=[
            OpenApiExample(
                'Chat request',
                value={
                    'tenant_id': 2,
                    'workspace_id': 3,
                    'question': 'What is the PTO policy?',
                    'top_k': 5,
                },
                request_only=True,
            ),
            OpenApiExample(
                'Chat response',
                value={
                    'answer': 'Employees accrue PTO each pay period and should submit requests through the employee portal.',
                    'sources': [
                        {
                            'chunk_id': 11,
                            'document_id': 123,
                            'document': 'Employee Handbook.pdf',
                            'chunk_index': 4,
                            'text': 'Paid time off is accrued each pay period...',
                            'distance': 0.09,
                            'source_url': 'https://drive.google.com/file/d/.../view',
                            'source_url_kind': 'external',
                        }
                    ],
                },
                response_only=True,
            ),
        ],
    )
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
            temperature=data.get('temperature'),
        )

        if isinstance(answer, dict):
            return Response({
                'answer': answer.get('answer', ''),
                'sources': answer.get('sources', []),
                'shipping_lookup': bool(answer.get('shipping_lookup')),
                'tracking_number': answer.get('tracking_number', ''),
            })

        return Response({
            'answer': answer,
            'sources': [_serialize_source(row) for row in results]
        })
