import requests
from django.conf import settings


class AgentMailError(Exception):
    pass


class AgentMailClient:
    def __init__(self, api_key=None, inbox_id=None, base_url=None):
        self.api_key = api_key or settings.AGENTMAIL_API_KEY
        self.inbox_id = inbox_id or settings.AGENTMAIL_INBOX_ID
        self.base_url = (base_url or settings.AGENTMAIL_BASE_URL).rstrip('/')
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

        response = requests.post(
            f'{self.base_url}/inboxes/{self.inbox_id}/messages',
            headers=self._headers(),
            json=payload,
            timeout=30,
        )

        try:
            data = response.json()
        except Exception:
            data = {'raw': response.text[:1000]}

        if response.status_code >= 400:
            raise AgentMailError(f'AgentMail send failed ({response.status_code}): {data}')

        return data
