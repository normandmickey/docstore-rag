import hashlib

from django.utils import timezone

from .models import APIKey


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256((raw_key or '').encode('utf-8')).hexdigest()


def get_api_key_from_header(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None
    raw_key = auth_header.split(' ', 1)[1].strip()
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    api_key = APIKey.objects.select_related('tenant', 'workspace').filter(key_hash=key_hash, active=True).first()
    if api_key:
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=['last_used_at'])
    return api_key
