from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone


AUTH_BASE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize'
TOKEN_BASE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
GRAPH_ME_URL = 'https://graph.microsoft.com/v1.0/me'

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'

ATLASSIAN_AUTH_URL = 'https://auth.atlassian.com/authorize'
ATLASSIAN_TOKEN_URL = 'https://auth.atlassian.com/oauth/token'
ATLASSIAN_ACCESSIBLE_RESOURCES_URL = 'https://api.atlassian.com/oauth/token/accessible-resources'
ATLASSIAN_USERINFO_URL = 'https://api.atlassian.com/me'

ZOOM_AUTH_URL = 'https://zoom.us/oauth/authorize'
ZOOM_TOKEN_URL = 'https://zoom.us/oauth/token'


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


def google_authorize_url(state):
    query = urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'scope': ' '.join(settings.GOOGLE_SCOPES),
        'state': state,
        'access_type': 'offline',
        'include_granted_scopes': 'true',
        'prompt': 'consent',
    })
    return f'{GOOGLE_AUTH_URL}?{query}'


def exchange_google_code_for_tokens(code):
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload


def refresh_google_tokens(refresh_token):
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload


def fetch_google_userinfo(access_token):
    response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def atlassian_authorize_url(state):
    query = urlencode({
        'audience': 'api.atlassian.com',
        'client_id': settings.ATLASSIAN_CLIENT_ID,
        'scope': ' '.join(settings.ATLASSIAN_SCOPES),
        'redirect_uri': settings.ATLASSIAN_REDIRECT_URI,
        'state': state,
        'response_type': 'code',
        'prompt': 'consent',
    })
    return f'{ATLASSIAN_AUTH_URL}?{query}'


def exchange_atlassian_code_for_tokens(code):
    response = requests.post(
        ATLASSIAN_TOKEN_URL,
        json={
            'grant_type': 'authorization_code',
            'client_id': settings.ATLASSIAN_CLIENT_ID,
            'client_secret': settings.ATLASSIAN_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.ATLASSIAN_REDIRECT_URI,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload


def fetch_atlassian_userinfo(access_token):
    response = requests.get(
        ATLASSIAN_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_atlassian_accessible_resources(access_token):
    response = requests.get(
        ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
        headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def zoom_authorize_url(state):
    query = urlencode({
        'response_type': 'code',
        'client_id': settings.ZOOM_CLIENT_ID,
        'redirect_uri': settings.ZOOM_REDIRECT_URI,
        'state': state,
    })
    return f'{ZOOM_AUTH_URL}?{query}'


def exchange_zoom_code_for_tokens(code):
    response = requests.post(
        ZOOM_TOKEN_URL,
        params={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.ZOOM_REDIRECT_URI,
        },
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload


def refresh_zoom_tokens(refresh_token):
    response = requests.post(
        ZOOM_TOKEN_URL,
        params={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        },
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload


def request_zoom_chatbot_token():
    response = requests.post(
        ZOOM_TOKEN_URL,
        params={
            'grant_type': 'client_credentials',
        },
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    expires_in = payload.get('expires_in', 3600)
    payload['expires_at'] = timezone.now() + timezone.timedelta(seconds=expires_in)
    return payload
