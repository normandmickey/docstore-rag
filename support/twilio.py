import os
from urllib.parse import urljoin

from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client


def twilio_enabled() -> bool:
    return bool((os.getenv('TWILIO_ACCOUNT_SID') or '').strip() and (os.getenv('TWILIO_AUTH_TOKEN') or '').strip())


def twilio_client() -> Client:
    account_sid = (os.getenv('TWILIO_ACCOUNT_SID') or '').strip()
    auth_token = (os.getenv('TWILIO_AUTH_TOKEN') or '').strip()
    if not account_sid or not auth_token:
        raise RuntimeError('Twilio credentials are not configured.')
    return Client(account_sid, auth_token)


def validate_twilio_request(request) -> bool:
    auth_token = (os.getenv('TWILIO_AUTH_TOKEN') or '').strip()
    if not auth_token:
        return False
    validator = RequestValidator(auth_token)
    signature = request.headers.get('X-Twilio-Signature', '')
    return validator.validate(request.build_absolute_uri(), request.POST, signature)


def status_callback_url() -> str:
    base = (os.getenv('TWILIO_WEBHOOK_BASE_URL') or '').strip().rstrip('/')
    if not base:
        return ''
    return urljoin(base + '/', 'twilio/webhooks/sms/status/')


def send_sms(*, from_number: str, to_number: str, body: str):
    client = twilio_client()
    kwargs = {
        'from_': from_number,
        'to': to_number,
        'body': body,
    }
    callback = status_callback_url()
    if callback:
        kwargs['status_callback'] = callback
    return client.messages.create(**kwargs)


__all__ = [
    'TwilioRestException',
    'send_sms',
    'status_callback_url',
    'twilio_enabled',
    'twilio_client',
    'validate_twilio_request',
]
