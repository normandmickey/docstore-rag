from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from control.api_auth import get_api_key_from_header

from .models import SupportChannel


class SupportChannelLookupSerializer(serializers.Serializer):
    phone_number = serializers.CharField()


class SupportChannelLookupView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Resolve a support channel by phone number',
        description='Look up the tenant/workspace context for an inbound support phone number. Used by support and voice integrations.',
        request=SupportChannelLookupSerializer,
        responses={
            200: OpenApiResponse(description='Support channel resolved.'),
            404: OpenApiResponse(description='Support channel not found.'),
        },
        examples=[
            OpenApiExample(
                'Support channel lookup request',
                value={'phone_number': '+17325551234'},
                request_only=True,
            ),
            OpenApiExample(
                'Support channel lookup response',
                value={
                    'channel': {
                        'id': 1,
                        'name': 'Main Support Line',
                        'type': 'sms',
                        'phone_number': '+17325551234',
                        'ai_enabled': True,
                        'auto_reply_enabled': True,
                    },
                    'tenant': {'id': 2, 'name': 'NJ Moore', 'slug': 'njmoore'},
                    'workspace': {'id': 3, 'name': 'Employee Docs', 'slug': 'employee-docs'},
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        api_key = get_api_key_from_header(request)
        if api_key is None:
            return Response({'detail': 'Authentication required.'}, status=401)

        serializer = SupportChannelLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = ''.join(ch for ch in serializer.validated_data['phone_number'].strip() if ch.isdigit() or ch == '+')

        channel = SupportChannel.objects.select_related('tenant', 'default_workspace').filter(
            twilio_phone_number=phone_number,
            active=True,
        ).first()
        if channel is None:
            return Response({'detail': 'Support channel not found.'}, status=404)

        return Response({
            'channel': {
                'id': channel.id,
                'name': channel.name,
                'type': channel.channel_type,
                'phone_number': channel.twilio_phone_number,
                'ai_enabled': channel.ai_enabled,
                'auto_reply_enabled': channel.auto_reply_enabled,
            },
            'tenant': {
                'id': channel.tenant_id,
                'name': channel.tenant.name,
                'slug': channel.tenant.slug,
            },
            'workspace': {
                'id': channel.default_workspace_id,
                'name': channel.default_workspace.name if channel.default_workspace else None,
                'slug': channel.default_workspace.slug if channel.default_workspace else None,
            },
        })
