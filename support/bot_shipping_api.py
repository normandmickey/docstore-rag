from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from control.api_guard import resolve_tenant_context
from retrieval.service import shipping_answer_payload


class BotShippingLookupSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    query = serializers.CharField()
    limit = serializers.IntegerField(required=False, default=3, min_value=1, max_value=10)


class BotShippingLookupView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Resolve shipping-style bot queries',
        description='Dedicated shipping-manager lookup path for chatbots and support flows. Uses the tenant shipping manager when configured.',
        request=BotShippingLookupSerializer,
        responses={200: OpenApiResponse(description='Shipping lookup response returned.')},
        examples=[
            OpenApiExample(
                'Bot shipping lookup request',
                value={'tenant_id': 2, 'workspace_id': 3, 'query': 'Where is package 478226002176?'},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = BotShippingLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, _workspace, _api_key = resolve_tenant_context(
            request,
            tenant_id=data.get('tenant_id'),
        )
        payload = shipping_answer_payload(
            tenant=tenant,
            query=data['query'].strip(),
            limit=data.get('limit', 3),
        )
        if payload is None:
            return Response({'handled': False, 'answer': '', 'sources': []})
        return Response({'handled': True, **payload})
