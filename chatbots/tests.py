from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from chatbots.api import (
    ChatbotConversationContextView,
    ChatbotEventIngestView,
    ChatbotMessageIngestView,
    ChatbotReplyRewriteView,
    ChatbotResolveView,
)


class ChatbotApiAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_resolve_requires_authentication(self):
        request = self.factory.post('/api/v1/chatbots/resolve/', {
            'platform': 'telegram',
        }, format='json')
        response = ChatbotResolveView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', str(response.data))

    def test_context_requires_authentication(self):
        request = self.factory.post('/api/v1/chatbots/context/', {
            'integration_id': 1,
            'external_conversation_id': 'conv-1',
        }, format='json')
        response = ChatbotConversationContextView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', str(response.data))

    def test_rewrite_requires_authentication(self):
        request = self.factory.post('/api/v1/chatbots/rewrite-reply/', {
            'answer_text': 'Draft answer',
            'user_text': 'Question',
        }, format='json')
        response = ChatbotReplyRewriteView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', str(response.data))

    def test_event_ingest_requires_authentication_without_workspace_context(self):
        request = self.factory.post('/api/v1/chatbots/events/ingest/', {
            'event_type': 'runner.started',
            'message': 'Started',
        }, format='json')
        response = ChatbotEventIngestView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', str(response.data))

    def test_message_ingest_requires_authentication_without_workspace_context(self):
        request = self.factory.post('/api/v1/chatbots/messages/ingest/', {
            'integration_id': 1,
            'platform': 'telegram',
            'direction': 'inbound',
        }, format='json')
        response = ChatbotMessageIngestView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', str(response.data))

    @patch('chatbots.api.resolve_request_context')
    def test_event_ingest_returns_403_when_workspace_context_resolution_denied(self, mock_resolve):
        mock_resolve.side_effect = PermissionDenied('Authentication required.')
        request = self.factory.post('/api/v1/chatbots/events/ingest/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'event_type': 'runner.started',
        }, format='json')
        response = ChatbotEventIngestView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Authentication required', str(response.data))
