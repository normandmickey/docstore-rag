from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from support.api import SupportChannelLookupView
from support.bot_shipping_api import BotShippingLookupView
from support.shipping_api import (
    ShippingHealthView,
    ShippingLatestStatusView,
    ShippingPackageDetailView,
    ShippingPackageSearchView,
)


class SupportApiAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User(id=1, username='norm')

    def test_support_channel_lookup_requires_authentication(self):
        request = self.factory.post('/api/v1/support/channel-lookup/', {
            'phone_number': '+15551230000',
        }, format='json')
        response = SupportChannelLookupView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', str(response.data))

    @patch('support.bot_shipping_api.resolve_tenant_context')
    @patch('support.bot_shipping_api.shipping_answer_payload')
    def test_bot_shipping_lookup_passes_tenant_context(self, mock_shipping, mock_resolve):
        tenant = object()
        mock_resolve.return_value = (tenant, None, object())
        mock_shipping.return_value = {
            'answer': 'Package delivered.',
            'sources': [],
            'tracking_number': '123',
        }

        request = self.factory.post('/api/v1/support/shipping/bot-lookup/', {
            'tenant_id': 5,
            'query': 'Where is package 123?',
        }, format='json')
        request.user = AnonymousUser()

        response = BotShippingLookupView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['handled'])
        mock_resolve.assert_called_once()
        self.assertEqual(mock_resolve.call_args.kwargs['tenant_id'], 5)

    @patch('support.shipping_api.resolve_request_context')
    def test_shipping_health_returns_403_for_non_admin_signed_in_user(self, mock_resolve):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)

        request = self.factory.post('/api/v1/support/shipping/health/', {
            'tenant_id': 1,
            'workspace_id': 2,
        }, format='json')
        request.user = self.user

        with patch('support.shipping_api.TenantMembership.objects.filter') as mock_membership_filter:
            mock_membership_filter.return_value.first.return_value = None
            response = ShippingHealthView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('Tenant admin access required', str(response.data))

    @patch('support.shipping_api.resolve_request_context')
    def test_shipping_search_returns_403_for_non_admin_signed_in_user(self, mock_resolve):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)

        request = self.factory.post('/api/v1/support/shipping/search/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'query': 'Norman Moore',
        }, format='json')
        request.user = self.user

        with patch('support.shipping_api.TenantMembership.objects.filter') as mock_membership_filter:
            mock_membership_filter.return_value.first.return_value = None
            response = ShippingPackageSearchView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('Tenant admin access required', str(response.data))

    @patch('support.shipping_api.resolve_request_context')
    def test_shipping_detail_returns_403_for_non_admin_signed_in_user(self, mock_resolve):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)

        request = self.factory.post('/api/v1/support/shipping/package/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'tracking_number': '123',
        }, format='json')
        request.user = self.user

        with patch('support.shipping_api.TenantMembership.objects.filter') as mock_membership_filter:
            mock_membership_filter.return_value.first.return_value = None
            response = ShippingPackageDetailView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('Tenant admin access required', str(response.data))

    @patch('support.shipping_api.resolve_request_context')
    def test_shipping_latest_status_returns_403_for_non_admin_signed_in_user(self, mock_resolve):
        tenant = object()
        workspace = object()
        mock_resolve.return_value = (tenant, workspace, None)

        request = self.factory.post('/api/v1/support/shipping/latest-status/', {
            'tenant_id': 1,
            'workspace_id': 2,
            'tracking_number': '123',
        }, format='json')
        request.user = self.user

        with patch('support.shipping_api.TenantMembership.objects.filter') as mock_membership_filter:
            mock_membership_filter.return_value.first.return_value = None
            response = ShippingLatestStatusView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('Tenant admin access required', str(response.data))
