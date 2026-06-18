from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase
from rest_framework.test import APIRequestFactory

from support.email_api import AgentMailInboundWebhookView
from support.orchestration import handle_support_request
from support.capabilities import classify_answer_signal, is_no_answer_response, try_knowledge_capability
from support.reply_composer import compose_acknowledgement, compose_support_reply
from support.reply_result import SupportReplyResult
from support.views import support_conversation_detail


class SupportReplyComposerTests(SimpleTestCase):
    def test_compose_shipping_email_reply_adds_intro(self):
        result = SupportReplyResult(
            mode='shipping',
            handled=True,
            should_reply=True,
            reply_text='Your package is in transit.',
        )
        rendered = compose_support_reply(result=result, channel='email')
        self.assertEqual(rendered, 'Thanks for reaching out.\n\nYour package is in transit.')

    def test_compose_knowledge_email_reply_adds_intro(self):
        result = SupportReplyResult(
            mode='knowledge',
            handled=True,
            should_reply=True,
            reply_text='The handbook says PTO accrues monthly.',
        )
        rendered = compose_support_reply(result=result, channel='email')
        self.assertEqual(rendered, 'Thanks for your email.\n\nThe handbook says PTO accrues monthly.')

    def test_compose_acknowledgement_for_email(self):
        rendered = compose_acknowledgement(channel='email', subject='Need help')
        self.assertIn('Thanks for your email.', rendered)
        self.assertIn("'Need help'", rendered)


class SupportOrchestrationTests(SimpleTestCase):
    def test_empty_query_returns_ack_and_handoff(self):
        result = handle_support_request(
            tenant=object(),
            workspace=None,
            channel='email',
            conversation=None,
            contact=None,
            user_text='',
            subject='',
        )
        self.assertEqual(result.mode, 'ack')
        self.assertTrue(result.should_reply)
        self.assertTrue(result.should_handoff)
        self.assertEqual(result.handoff_reason, 'empty_query')

    @patch('support.orchestration.try_shipping_capability')
    def test_shipping_query_returns_shipping_result(self, mock_shipping):
        mock_shipping.return_value = SupportReplyResult(
            mode='shipping',
            handled=True,
            should_reply=True,
            reply_text='Package 123 is delivered.',
        )
        result = handle_support_request(
            tenant=object(),
            workspace=None,
            channel='email',
            conversation=None,
            contact=None,
            user_text='Where is package 123?',
            subject='Package help',
        )
        self.assertEqual(result.mode, 'shipping')
        self.assertTrue(result.should_reply)
        self.assertIn('Thanks for reaching out.', result.reply_text)
        mock_shipping.assert_called_once()

    @patch('support.orchestration.try_knowledge_capability')
    def test_knowledge_query_returns_knowledge_result(self, mock_knowledge):
        mock_knowledge.return_value = SupportReplyResult(
            mode='knowledge',
            handled=True,
            should_reply=True,
            reply_text='Employees get paid holidays listed in the handbook.',
        )
        result = handle_support_request(
            tenant=object(),
            workspace=object(),
            channel='email',
            conversation=None,
            contact=None,
            user_text='What are the paid holidays?',
            subject='Holiday policy',
        )
        self.assertEqual(result.mode, 'knowledge')
        self.assertTrue(result.should_reply)
        self.assertIn('Thanks for your email.', result.reply_text)
        mock_knowledge.assert_called_once()

    @patch('support.orchestration.try_knowledge_capability')
    @patch('support.orchestration.try_shipping_capability')
    def test_no_answer_falls_back_to_ack(self, mock_shipping, mock_knowledge):
        mock_shipping.return_value = SupportReplyResult(
            mode='shipping',
            handled=False,
            should_reply=False,
            reply_text='',
        )
        mock_knowledge.return_value = SupportReplyResult(
            mode='knowledge',
            handled=False,
            should_reply=False,
            reply_text='',
            retrieval_metadata={'result_count': 0},
        )
        result = handle_support_request(
            tenant=object(),
            workspace=object(),
            channel='email',
            conversation=None,
            contact=None,
            user_text='I need help with something weird',
            subject='Odd issue',
        )
        self.assertEqual(result.mode, 'ack')
        self.assertTrue(result.should_reply)
        self.assertTrue(result.should_handoff)
        self.assertEqual(result.handoff_reason, 'no_confident_auto_answer')
        self.assertIn('Thanks for your email.', result.reply_text)
        self.assertEqual(result.retrieval_metadata.get('result_count'), 0)

    @patch('support.orchestration.try_knowledge_capability')
    @patch('support.orchestration.try_shipping_capability')
    def test_dashboard_chat_no_answer_uses_document_grounded_fallback(self, mock_shipping, mock_knowledge):
        mock_shipping.return_value = SupportReplyResult(
            mode='shipping',
            handled=False,
            should_reply=False,
            reply_text='',
        )
        mock_knowledge.return_value = SupportReplyResult(
            mode='knowledge',
            handled=False,
            should_reply=False,
            reply_text='',
            retrieval_metadata={'result_count': 0},
        )
        result = handle_support_request(
            tenant=object(),
            workspace=object(),
            channel='dashboard_chat',
            conversation=None,
            contact=None,
            user_text='Something obscure',
            subject='',
        )
        self.assertEqual(result.mode, 'ack')
        self.assertEqual(result.reply_text, 'I could not find a confident answer in the current workspace documents yet.')
        self.assertTrue(result.should_handoff)


class KnowledgeNoAnswerDetectionTests(SimpleTestCase):
    @patch('support.capabilities.answer_question')
    def test_try_knowledge_capability_detects_documents_do_not_contain_phrase(self, mock_answer_question):
        mock_answer_question.return_value = (
            'I’m sorry, but the documents you provided do not contain any specific information about a reimbursement policy for coworking spaces.',
            [],
        )
        result = try_knowledge_capability(
            tenant=object(),
            workspace=object(),
            query='What is the reimbursement policy for coworking spaces?',
        )
        self.assertFalse(result.handled)
        self.assertFalse(result.should_reply)
        self.assertTrue(result.capability_metadata.get('no_answer_detected'))

    @patch('support.capabilities.answer_question')
    def test_try_knowledge_capability_detects_not_sure_based_on_documents_phrase(self, mock_answer_question):
        mock_answer_question.return_value = (
            'I’m not sure based on the documents you shared. None of the excerpts or facts mention a policy about reimbursing home-office furniture.',
            [],
        )
        result = try_knowledge_capability(
            tenant=object(),
            workspace=object(),
            query='Can I expense home office furniture?',
        )
        self.assertFalse(result.handled)
        self.assertFalse(result.should_reply)
        self.assertTrue(result.capability_metadata.get('no_answer_detected'))

    @patch('support.capabilities.answer_question')
    def test_try_knowledge_capability_detects_not_aware_and_excerpts_discuss_phrase(self, mock_answer_question):
        mock_answer_question.return_value = (
            'I’m not aware of any rule in the supplied documents that addresses home-office furniture specifically. None of the provided excerpts discuss home-office furniture expenses.',
            [],
        )
        result = try_knowledge_capability(
            tenant=object(),
            workspace=object(),
            query='Can I expense home office furniture?',
        )
        self.assertFalse(result.handled)
        self.assertFalse(result.should_reply)
        self.assertTrue(result.capability_metadata.get('no_answer_detected'))


class NoAnswerPatternTests(SimpleTestCase):
    def test_classify_answer_signal_marks_soft_no_information_language(self):
        self.assertEqual(
            classify_answer_signal(
                'I don’t have information on a specific reimbursement policy for coworking spaces based on the documents provided.'
            ),
            'soft',
        )

    def test_is_no_answer_response_soft_signal_with_weak_results(self):
        weak = [SimpleNamespace(blended_score=0.22)]
        self.assertTrue(
            is_no_answer_response(
                'I don’t have information on a specific reimbursement policy for coworking spaces based on the documents provided.',
                results=weak,
            )
        )

    def test_is_no_answer_response_soft_signal_with_stronger_results(self):
        strong = [SimpleNamespace(blended_score=0.41)]
        self.assertFalse(
            is_no_answer_response(
                'I don’t have information on a specific reimbursement policy for coworking spaces based on the documents provided.',
                results=strong,
            )
        )

    def test_is_no_answer_response_matches_no_mention_language(self):
        self.assertEqual(
            classify_answer_signal(
                'There is no mention in the provided documents of a waiting period for dental coverage.'
            ),
            'soft',
        )

    def test_is_no_answer_response_matches_documents_do_not_contain_language(self):
        self.assertTrue(
            is_no_answer_response(
                'The documents provided do not contain any statement that employees may work a hybrid schedule.'
            )
        )


class SupportConversationSuggestionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User(id=1, username='norm')

    @patch('support.views.render')
    @patch('support.views.messages.success')
    @patch('support.views.handle_support_request')
    @patch('support.views.SupportConversationUpdateForm')
    @patch('support.views._handle_workspace_actions', return_value=None)
    @patch('support.views._dashboard_base')
    @patch('support.views.get_object_or_404')
    def test_support_conversation_suggest_reply_prefills_form(
        self,
        mock_get_object,
        mock_base,
        _mock_handle_actions,
        mock_update_form,
        mock_handle_support,
        mock_message_success,
        mock_render,
    ):
        inbound_message = SimpleNamespace(body='What is the PTO policy?')
        messages_manager = MagicMock()
        messages_manager.filter.return_value.order_by.return_value.first.return_value = inbound_message

        conversation = SimpleNamespace(
            id=123,
            tenant=object(),
            channel=SimpleNamespace(channel_type='email'),
            contact=object(),
            workspace_context=object(),
            subject='PTO question',
            messages=messages_manager,
        )
        mock_get_object.return_value = conversation
        mock_base.return_value = {
            'current_tenant': object(),
            'can_manage_tenant': True,
        }
        mock_update_form.return_value = MagicMock()
        mock_handle_support.return_value = SupportReplyResult(
            mode='knowledge',
            handled=True,
            should_reply=True,
            reply_text='Here is a suggested answer.',
        )

        request = self.factory.post('/dashboard/support/conversations/123/', {
            'action': 'reply',
            'body': '',
            'suggest_reply': '1',
        })
        request.user = self.user
        request.session = {}

        response = support_conversation_detail(request, 123)

        self.assertEqual(response, mock_render.return_value)
        kwargs = mock_render.call_args[0][2]
        self.assertEqual(kwargs['support_reply_form'].initial['body'], 'Here is a suggested answer.')
        mock_message_success.assert_called_once()


class AgentMailWebhookTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch('support.email_api.send_support_email_reply')
    @patch('support.email_api.handle_support_request')
    @patch('support.email_api.ingest_inbound_email')
    @patch('support.email_api.TenantEmailIntegration.objects.filter')
    def test_agentmail_webhook_auto_reply_uses_orchestrator(
        self,
        mock_filter,
        mock_ingest,
        mock_handle_support,
        mock_send_reply,
    ):
        integration = SimpleNamespace(
            id=7,
            tenant=object(),
            tenant_id=5,
            inbox_id='inbox-123',
            provider='agentmail',
            status='active',
            auto_reply_enabled=True,
            default_workspace=object(),
        )
        conversation = SimpleNamespace(
            id=11,
            contact=object(),
            workspace_context=integration.default_workspace,
            metadata_json={},
            save=MagicMock(),
        )
        message = SimpleNamespace(id=12)

        mock_filter.return_value.first.return_value = integration
        mock_ingest.return_value = (conversation, message)
        mock_handle_support.return_value = SupportReplyResult(
            mode='knowledge',
            handled=True,
            should_reply=True,
            reply_text='Here is the auto reply.',
        )

        request = self.factory.post('/api/v1/support/email/agentmail/inbound/', {
            'inbox_id': 'inbox-123',
            'message_id': 'msg-1',
            'thread_id': 'thread-1',
            'subject': 'Need handbook help',
            'text': 'What is the PTO policy?',
            'from_email': 'user@example.com',
            'from_name': 'User',
            'event_type': 'message.received',
        }, format='json')

        response = AgentMailInboundWebhookView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['auto_reply_sent'])
        self.assertEqual(response.data['auto_reply_mode'], 'knowledge')
        mock_handle_support.assert_called_once()
        mock_send_reply.assert_called_once_with(conversation=conversation, body='Here is the auto reply.')
