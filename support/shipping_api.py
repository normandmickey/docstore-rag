from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from control.api_guard import resolve_request_context
from control.models import TenantMembership

from .shipping import ShippingManagerClient, ShippingManagerError, ShippingManagerNotConfigured


class ShippingHealthSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)


class ShippingPackageSearchSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    query = serializers.CharField()
    limit = serializers.IntegerField(required=False, default=10, min_value=1, max_value=25)


class ShippingTrackingSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    workspace_id = serializers.IntegerField(required=False)
    tracking_number = serializers.CharField()


class TenantScopedSupportAPIView(APIView):
    permission_classes = [AllowAny]

    def resolve_and_authorize(self, request, *, tenant_id=None, workspace_id=None):
        tenant, workspace, _api_key = resolve_request_context(
            request,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        if request.user.is_authenticated:
            membership = TenantMembership.objects.filter(user=request.user, tenant=tenant).first()
            if membership is None or membership.role not in {TenantMembership.ROLE_OWNER, TenantMembership.ROLE_ADMIN}:
                return None, None, Response({'detail': 'Tenant admin access required.'}, status=403)
        return tenant, workspace, None


class ShippingHealthView(TenantScopedSupportAPIView):
    @extend_schema(
        summary='Check shipping manager health',
        description='Verify Docstore can reach the internal shipping manager service.',
        request=ShippingHealthSerializer,
        responses={200: OpenApiResponse(description='Shipping manager is reachable.')},
        examples=[
            OpenApiExample(
                'Health response',
                value={'ok': True, 'shipping_manager': {'ok': True, 'service': 'fedexsucks', 'api': 'internal'}},
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ShippingHealthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _tenant, _workspace, denied = self.resolve_and_authorize(
            request,
            tenant_id=serializer.validated_data.get('tenant_id'),
            workspace_id=serializer.validated_data.get('workspace_id'),
        )
        if denied is not None:
            return denied
        try:
            client = ShippingManagerClient.for_tenant(_tenant)
            return Response({'ok': True, 'shipping_manager': client.health()})
        except ShippingManagerNotConfigured as exc:
            return Response({'detail': str(exc)}, status=503)
        except ShippingManagerError as exc:
            return Response({'detail': str(exc)}, status=502)


class ShippingPackageSearchView(TenantScopedSupportAPIView):
    @extend_schema(
        summary='Search shipping manager packages',
        description='Search trusted shipping records via the internal shipping manager instead of hitting carrier APIs directly from Docstore.',
        request=ShippingPackageSearchSerializer,
        responses={200: OpenApiResponse(description='Shipping search results returned.')},
        examples=[
            OpenApiExample(
                'Shipping search request',
                value={'tenant_id': 2, 'workspace_id': 3, 'query': 'Norman Moore 14823', 'limit': 5},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ShippingPackageSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        _tenant, _workspace, denied = self.resolve_and_authorize(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        if denied is not None:
            return denied
        try:
            client = ShippingManagerClient.for_tenant(_tenant)
            payload = client.search_packages(data['query'].strip(), limit=data.get('limit', 10))
            return Response(payload)
        except ShippingManagerNotConfigured as exc:
            return Response({'detail': str(exc)}, status=503)
        except ShippingManagerError as exc:
            return Response({'detail': str(exc)}, status=502)


class ShippingPackageDetailView(TenantScopedSupportAPIView):
    @extend_schema(
        summary='Fetch shipping package detail',
        description='Fetch stored package detail from the internal shipping manager.',
        request=ShippingTrackingSerializer,
        responses={200: OpenApiResponse(description='Package detail returned.')},
    )
    def post(self, request):
        serializer = ShippingTrackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        _tenant, _workspace, denied = self.resolve_and_authorize(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        if denied is not None:
            return denied
        try:
            client = ShippingManagerClient.for_tenant(_tenant)
            payload = client.get_package(data['tracking_number'].strip())
            return Response(payload)
        except ShippingManagerNotConfigured as exc:
            return Response({'detail': str(exc)}, status=503)
        except ShippingManagerError as exc:
            return Response({'detail': str(exc)}, status=502)


class ShippingLatestStatusView(TenantScopedSupportAPIView):
    @extend_schema(
        summary='Fetch latest package status',
        description='Fetch the latest stored package status from the internal shipping manager.',
        request=ShippingTrackingSerializer,
        responses={200: OpenApiResponse(description='Latest package status returned.')},
    )
    def post(self, request):
        serializer = ShippingTrackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        _tenant, _workspace, denied = self.resolve_and_authorize(
            request,
            tenant_id=data.get('tenant_id'),
            workspace_id=data.get('workspace_id'),
        )
        if denied is not None:
            return denied
        try:
            client = ShippingManagerClient.for_tenant(_tenant)
            payload = client.get_latest_status(data['tracking_number'].strip())
            return Response(payload)
        except ShippingManagerNotConfigured as exc:
            return Response({'detail': str(exc)}, status=503)
        except ShippingManagerError as exc:
            return Response({'detail': str(exc)}, status=502)
