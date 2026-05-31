import requests
from django.conf import settings


class AgentMailError(Exception):
    pass


class AgentMailClient:
    def __init__(self, api_key=None, inbox_id=None, base_url=None):
        self.api_key = api_key or settings.AGENTMAIL_API_KEY
        self.inbox_id = inbox_id or settings.AGENTMAIL_INBOX_ID
        raw_base_url = (base_url or settings.AGENTMAIL_BASE_URL or 'https://api.agentmail.to').rstrip('/')
        if raw_base_url.endswith('/v0'):
            self.base_url = raw_base_url[:-3]
            self.api_prefix = '/v0'
        else:
            self.base_url = raw_base_url
            self.api_prefix = '/v0'
        if not self.api_key:
            raise AgentMailError('AGENTMAIL_API_KEY is not configured.')
        if not self.inbox_id:
            raise AgentMailError('AGENTMAIL_INBOX_ID is not configured.')

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def send_message(self, *, to, subject, text='', html=''):
        if not to:
            raise AgentMailError('Recipient email is required.')
        if not subject:
            raise AgentMailError('Email subject is required.')
        if not text and not html:
            raise AgentMailError('Email body is required.')

        payload = {
            'to': [to] if isinstance(to, str) else list(to),
            'subject': subject,
        }
        if text:
            payload['text'] = text
        if html:
            payload['html'] = html

        candidate_urls = [
            f'{self.base_url}{self.api_prefix}/inboxes/{self.inbox_id}/messages',
            f'{self.base_url}/v0/inboxes/{self.inbox_id}/messages',
            f'https://api.agentmail.to/v0/inboxes/{self.inbox_id}/messages',
        ]

        last_error = None
        for url in dict.fromkeys(candidate_urls):
            response = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=30,
            )

            try:
                data = response.json()
            except Exception:
                data = {'raw': response.text[:1000]}

            if response.status_code < 400:
                return data

            last_error = f'AgentMail send failed via {url} ({response.status_code}): {data}'
            if response.status_code != 404:
                raise AgentMailError(last_error)

        raise AgentMailError(last_error or 'AgentMail send failed.')
