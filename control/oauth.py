from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime


AUTH_BASE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize'
TOKEN_BASE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
GRAPH_ME_URL = 'https://graph.microsoft.com/v1.0/me'


def microsoft_authorize_url(state):
    query = urlencode({
        'client_id': settings.MS_GRAPH_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': settings.MS_GRAPH_REDIRECT_URI,
        'response_mode': 'query',
        'scope': ' '.join(settings.MS_GRAPH_SCOPES),
        'state': state,
    })
    return f"{AUTH_BASE.format(tenant=settings.MS_GRAPH_TENANT_ID)}?{query}"


def exchange_code_for_tokens(code):
    response = requests.post(
        TOKEN_BASE.format(tenant=settings.MS_GRAPH_TENANT_ID),
        data={
            'client_id': settings.MS_GRAPH_CLIENT_ID,
            'client_secret': settings.MS_GRAPH_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.MS_GRAPH_REDIRECT_URI,
            'grant_type': 'authorization_code',
            'scope': ' '.join(settings.MS_GRAPH_SCOPES),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload


def fetch_graph_me(access_token):
    response = requests.get(
        GRAPH_ME_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
