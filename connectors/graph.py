import requests
from django.conf import settings


class SharePointGraphClient:
    def __init__(self, tenant_id=None, client_id=None, client_secret=None):
        self.tenant_id = tenant_id or settings.MS_GRAPH_TENANT_ID
        self.client_id = client_id or settings.MS_GRAPH_CLIENT_ID
        self.client_secret = client_secret or settings.MS_GRAPH_CLIENT_SECRET
        self.base_url = 'https://graph.microsoft.com/v1.0'

    def _token(self):
        token_url = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token'
        response = requests.post(
            token_url,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials',
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()['access_token']

    def _headers(self):
        return {'Authorization': f'Bearer {self._token()}'}

    def list_children(self, drive_id, item_id='root'):
        response = requests.get(
            f'{self.base_url}/drives/{drive_id}/items/{item_id}/children',
            headers=self._headers(),
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get('value', [])

    def download_content(self, drive_id, item_id):
        response = requests.get(
            f'{self.base_url}/drives/{drive_id}/items/{item_id}/content',
            headers=self._headers(),
            timeout=120,
        )
        response.raise_for_status()
        return response.content
