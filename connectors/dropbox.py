import json

import requests


class DropboxAPIError(Exception):
    pass


class DropboxClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.api_url = 'https://api.dropboxapi.com/2'
        self.content_url = 'https://content.dropboxapi.com/2'

    def _headers(self):
        return {'Authorization': f'Bearer {self.access_token}'}

    def _raise_for_status(self, response):
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            details = response.text[:500]
            try:
                payload = response.json() or {}
                details = payload.get('error_summary') or payload.get('error', {}).get('.tag') or details
            except Exception:
                pass
            raise DropboxAPIError(details or str(exc)) from exc

    def list_folder(self, path=''):
        response = requests.post(
            f'{self.api_url}/files/list_folder',
            headers={**self._headers(), 'Content-Type': 'application/json'},
            json={
                'path': path,
                'recursive': False,
                'include_mounted_folders': True,
            },
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json().get('entries', [])

    def download_file_bytes(self, path):
        response = requests.post(
            f'{self.content_url}/files/download',
            headers={
                **self._headers(),
                'Dropbox-API-Arg': json.dumps({'path': path}),
            },
            timeout=120,
        )
        self._raise_for_status(response)
        metadata = json.loads(response.headers.get('Dropbox-API-Result', '{}') or '{}')
        return response.content, metadata
