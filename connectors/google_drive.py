import requests


class GoogleDriveClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = 'https://www.googleapis.com/drive/v3'

    def _headers(self):
        return {'Authorization': f'Bearer {self.access_token}'}

    def list_files(self, q=None, page_size=25):
        params = {
            'pageSize': page_size,
            'fields': 'files(id,name,mimeType,modifiedTime,parents,webViewLink,iconLink)',
            'supportsAllDrives': 'true',
            'includeItemsFromAllDrives': 'true',
            'orderBy': 'modifiedTime desc',
        }
        if q:
            params['q'] = q
        response = requests.get(
            f'{self.base_url}/files',
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get('files', [])
