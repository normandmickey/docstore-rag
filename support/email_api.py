from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .email_services import TenantEmailIntegrationError, ingest_inbound_email
from .models import TenantEmailIntegration


class AgentMailInboundSerializer(serializers.Serializer):
    inbox_id = serializers.CharField(required=False, allow_blank=True)
    message_id = serializers.CharField(required=False, allow_blank=True)
    subject = serializers.CharField(required=False, allow_blank=True)
    text = serializers.CharField(required=False, allow_blank=True)
    html = serializers.CharField(required=False, allow_blank=True)
    from_email = serializers.EmailField(required=False, allow_blank=True)
    from_name = serializers.CharField(required=False, allow_blank=True)
    payload_json = serializers.JSONField(required=False)


class AgentMailInboundWebhookView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Receive inbound AgentMail events for tenant support email',
        description='Lightweight webhook entry point for AgentMail-backed tenant email support. Maps inbound emails into support conversations.',
        request=AgentMailInboundSerializer,
        responses={200: OpenApiResponse(description='Inbound email processed.')},
        examples=[
            OpenApiExample(
                'Inbound support email',
                value={
                    'inbox_id': 'support-inbox-id',
                    'message_id': 'msg_123',
                    'subject': 'Need help with onboarding',
                    'text': 'Can someone call me back?',
                    'from_email': 'customer@example.com',
                    'from_name': 'Customer Name',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = AgentMailInboundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        integration = TenantEmailIntegration.objects.filter(
            inbox_id=(data.get('inbox_id') or '').strip(),
            provider=TenantEmailIntegration.PROVIDER_AGENTMAIL,
            status=TenantEmailIntegration.STATUS_ACTIVE,
        ).first()
        if integration is None:
            return Response({'detail': 'No active tenant email integration found for that inbox.'}, status=404)

        payload_json = data.get('payload_json') or {}
        from_email = (data.get('from_email') or payload_json.get('from_email') or '').strip().lower()
        from_name = (data.get('from_name') or payload_json.get('from_name') or '').strip()
        subject = (data.get('subject') or payload_json.get('subject') or '').strip()
        body_text = (data.get('text') or payload_json.get('text') or data.get('html') or '').strip()
        provider_message_id = (data.get('message_id') or payload_json.get('message_id') or '').strip()

        try:
            conversation, message = ingest_inbound_email(
                integration=integration,
                from_email=from_email,
                from_name=from_name,
                subject=subject,
                body_text=body_text,
                provider_message_id=provider_message_id,
            )
        except TenantEmailIntegrationError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response({
            'ok': True,
            'conversation_id': conversation.id,
            'message_id': message.id,
            'tenant_id': integration.tenant_id,
        })
