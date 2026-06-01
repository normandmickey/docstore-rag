import requests


class ConfluenceClient:
    def __init__(self, *, access_token: str, cloud_id: str):
        self.access_token = access_token
        self.cloud_id = cloud_id
        self.base_url = f'https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2'

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
        }

    def list_spaces(self, limit: int = 25):
        response = requests.get(
            f'{self.base_url}/spaces',
            params={'limit': limit},
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def list_pages(self, *, limit: int = 25, space_id: str | None = None, title: str | None = None):
        params = {'limit': limit}
        if space_id:
            params['space-id'] = space_id
        if title:
            params['title'] = title
        response = requests.get(
            f'{self.base_url}/pages',
            params=params,
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
