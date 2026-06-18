import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage

try:
    from storages.backends.s3 import S3Storage
except Exception:  # pragma: no cover
    S3Storage = None


class LocalDocumentStorage(FileSystemStorage):
    location = settings.MEDIA_ROOT
    base_url = settings.MEDIA_URL


if S3Storage and getattr(settings, 'USE_S3_STORAGE', False):
    class DocumentStorage(S3Storage):
        bucket_name = settings.S3_BUCKET
        default_acl = None
        file_overwrite = False
        querystring_auth = True
        custom_domain = None
        region_name = settings.S3_REGION
        endpoint_url = settings.S3_ENDPOINT_URL or None
    
else:
    class DocumentStorage(LocalDocumentStorage):
        pass
