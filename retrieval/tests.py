from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from retrieval.api import ChatView
from support.reply_result import SupportReplyResult


class ChatApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User(id=1, username='tester')

    @patch('retrieval.api.handle_support_request')
    @patch('retrieval.api.resolve_request_context')
    def test_chat_api_returns_knowledge_response_shape(self, mock_resolve, mock_handle):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)
        mock_handle.return_value = SupportReplyResult(
            mode='knowledge',
            handled=True,
            should_reply=True,
            reply_text='Here is the handbook answer.',
            sources=[{'document': 'Handbook.pdf', 'source_url': 'https://example.com/handbook'}],
            retrieval_metadata={'results': []},
            should_handoff=False,
            handoff_reason='',
        )

        request = self.factory.post('/api/v1/chat/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'question': 'What is the PTO policy?',
            'top_k': 5,
        }, format='json')
        request.user = self.user

        response = ChatView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['answer'], 'Here is the handbook answer.')
        self.assertEqual(response.data['mode'], 'knowledge')
        self.assertFalse(response.data['shipping_lookup'])
        self.assertFalse(response.data['should_handoff'])
        self.assertEqual(len(response.data['sources']), 1)

    @patch('retrieval.api.handle_support_request')
    @patch('retrieval.api.resolve_request_context')
    def test_chat_api_returns_shipping_response_shape(self, mock_resolve, mock_handle):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)
        mock_handle.return_value = SupportReplyResult(
            mode='shipping',
            handled=True,
            should_reply=True,
            reply_text='Package 123 is delivered.',
            sources=[{'tracking_number': '123'}],
            capability_metadata={'raw_payload': {'tracking_number': '123'}},
            should_handoff=False,
            handoff_reason='',
        )

        request = self.factory.post('/api/v1/chat/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'question': 'Where is package 123?',
            'top_k': 5,
        }, format='json')
        request.user = self.user

        response = ChatView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['answer'], 'Package 123 is delivered.')
        self.assertEqual(response.data['mode'], 'shipping')
        self.assertTrue(response.data['shipping_lookup'])
        self.assertEqual(response.data['tracking_number'], '123')

    @patch('retrieval.api.handle_support_request')
    @patch('retrieval.api.resolve_request_context')
    def test_chat_api_returns_handoff_metadata(self, mock_resolve, mock_handle):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)
        mock_handle.return_value = SupportReplyResult(
            mode='ack',
            handled=False,
            should_reply=True,
            reply_text='We received your request and will follow up shortly.',
            should_handoff=True,
            handoff_reason='no_confident_auto_answer',
            retrieval_metadata={'results': []},
        )

        request = self.factory.post('/api/v1/chat/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'question': 'Something unusual happened',
            'top_k': 5,
        }, format='json')
        request.user = self.user

        response = ChatView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mode'], 'ack')
        self.assertEqual(response.data['answer'], 'We received your request and will follow up shortly.')
        self.assertTrue(response.data['should_handoff'])
        self.assertEqual(response.data['handoff_reason'], 'no_confident_auto_answer')

    @patch('retrieval.api.resolve_request_context')
    def test_chat_api_returns_403_when_context_resolution_denied(self, mock_resolve):
        mock_resolve.side_effect = PermissionDenied('Authentication required.')

        request = self.factory.post('/api/v1/chat/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'question': 'What is the PTO policy?',
            'top_k': 5,
        }, format='json')
        request.user = AnonymousUser()

        response = ChatView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Authentication required', str(response.data))

    @patch('retrieval.api.handle_support_request')
    @patch('retrieval.api.resolve_request_context')
    def test_chat_api_passes_document_scope_to_orchestrator(self, mock_resolve, mock_handle):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)
        mock_handle.return_value = SupportReplyResult(
            mode='knowledge',
            handled=True,
            should_reply=True,
            reply_text='Scoped answer.',
            retrieval_metadata={'results': []},
        )

        request = self.factory.post('/api/v1/chat/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'question': 'What does this document say?',
            'top_k': 5,
            'document_id': 99,
        }, format='json')
        request.user = self.user

        response = ChatView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        mock_handle.assert_called_once()
        self.assertEqual(mock_handle.call_args.kwargs['document_id'], 99)
