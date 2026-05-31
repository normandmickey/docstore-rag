import requests


GOOGLE_DOC_EXPORTS = {
    'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
    'application/vnd.google-apps.spreadsheet': ('text/csv', '.csv'),
    'application/vnd.google-apps.presentation': ('application/pdf', '.pdf'),
}

SUPPORTED_GOOGLE_DRIVE_EXPORT_MIME_TYPES = set(GOOGLE_DOC_EXPORTS.keys())


class GoogleDriveClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = 'https://www.googleapis.com/drive/v3'

    def _headers(self):
        return {'Authorization': f'Bearer {self.access_token}'}

    def list_files(self, q=None, page_size=25):
        params = {
            'pageSize': page_size,
            'fields': 'files(id,name,mimeType,modifiedTime,parents,webViewLink,iconLink,size,md5Checksum)',
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

    def get_file(self, file_id):
        response = requests.get(
            f'{self.base_url}/files/{file_id}',
            headers=self._headers(),
            params={
                'fields': 'id,name,mimeType,modifiedTime,parents,webViewLink,iconLink,size,md5Checksum',
                'supportsAllDrives': 'true',
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def list_folder_files(self, folder_id='root', page_size=100):
        q = f"'{folder_id}' in parents and trashed = false"
        return self.list_files(q=q, page_size=page_size)

    def download_file_bytes(self, file_id, mime_type=None, filename=''):
        if mime_type in GOOGLE_DOC_EXPORTS:
            export_mime, ext = GOOGLE_DOC_EXPORTS[mime_type]
            response = requests.get(
                f'{self.base_url}/files/{file_id}/export',
                headers=self._headers(),
                params={'mimeType': export_mime},
                timeout=120,
            )
            response.raise_for_status()
            if filename and not filename.lower().endswith(ext):
                filename = f'{filename}{ext}'
            return response.content, export_mime, filename

        response = requests.get(
            f'{self.base_url}/files/{file_id}',
            headers=self._headers(),
            params={'alt': 'media', 'supportsAllDrives': 'true'},
            timeout=120,
        )
        response.raise_for_status()
        return response.content, mime_type or response.headers.get('Content-Type', ''), filename
