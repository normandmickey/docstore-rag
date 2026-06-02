from __future__ import annotations

import requests
from django.conf import settings

from connectors.models import TenantShippingIntegration


class ShippingManagerError(Exception):
    pass


class ShippingManagerNotConfigured(ShippingManagerError):
    pass


class ShippingManagerClient:
    def __init__(self, *, base_url: str | None = None, api_key: str | None = None, timeout: int = 20):
        self.base_url = (base_url or getattr(settings, 'SHIPPING_MANAGER_BASE_URL', '') or '').rstrip('/')
        self.api_key = (api_key or getattr(settings, 'SHIPPING_MANAGER_API_KEY', '') or '').strip()
        self.timeout = timeout
        if not self.base_url:
            raise ShippingManagerNotConfigured('SHIPPING_MANAGER_BASE_URL is not configured.')
        if not self.api_key:
            raise ShippingManagerNotConfigured('SHIPPING_MANAGER_API_KEY is not configured.')

    @classmethod
    def for_tenant(cls, tenant, *, timeout: int = 20):
        integration = TenantShippingIntegration.objects.filter(
            tenant=tenant,
            provider=TenantShippingIntegration.PROVIDER_FEDEXSUCKS,
            status=TenantShippingIntegration.STATUS_ACTIVE,
        ).first()
        if integration and integration.base_url and integration.api_key:
            return cls(base_url=integration.base_url, api_key=integration.api_key, timeout=timeout)
        return cls(timeout=timeout)

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json',
        }

    def _get(self, path: str, *, params: dict | None = None) -> dict:
        response = requests.get(
            f'{self.base_url}{path}',
            headers=self._headers(),
            params=params or {},
            timeout=self.timeout,
        )
        try:
            data = response.json()
        except Exception:
            data = {'detail': response.text[:1000]}
        if response.status_code >= 400:
            raise ShippingManagerError(data.get('detail') or f'Shipping manager request failed with status {response.status_code}.')
        return data

    def health(self) -> dict:
        return self._get('/api/internal/health/')

    def search_packages(self, query: str, *, limit: int = 10) -> dict:
        return self._get('/api/internal/packages/search/', params={'q': query, 'limit': limit})

    def get_package(self, tracking_number: str) -> dict:
        return self._get(f'/api/internal/packages/{tracking_number}/')

    def get_latest_status(self, tracking_number: str) -> dict:
        return self._get(f'/api/internal/packages/{tracking_number}/latest-status/')
