from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'storages',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'pgvector.django',
    'control',
    'documents',
    'ingestion',
    'retrieval',
    'audit',
    'connectors',
    'support',
    'integrations.voice',
    'chatbots',
    'reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/docstore_rag')

if DATABASE_URL.startswith('postgres'):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(DATABASE_URL)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': parsed.path.lstrip('/'),
                'USER': parsed.username,
                'PASSWORD': parsed.password,
                'HOST': parsed.hostname,
                'PORT': parsed.port or 5432,
            }
        }
    except Exception:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

DEFAULT_EMBEDDING_MODEL = os.getenv('DEFAULT_EMBEDDING_MODEL', 'text-embedding-3-large')
DEFAULT_CHAT_MODEL = os.getenv('DEFAULT_CHAT_MODEL', 'gpt-4.1-mini')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_BASE_URL = os.getenv('GROQ_BASE_URL', 'https://api.groq.com/openai/v1')
MS_GRAPH_TENANT_ID = os.getenv('MS_GRAPH_TENANT_ID', 'common')
MS_GRAPH_CLIENT_ID = os.getenv('MS_GRAPH_CLIENT_ID', '')
MS_GRAPH_CLIENT_SECRET = os.getenv('MS_GRAPH_CLIENT_SECRET', '')
MS_GRAPH_REDIRECT_URI = os.getenv('MS_GRAPH_REDIRECT_URI', '')
MS_GRAPH_SCOPES = [scope.strip() for scope in os.getenv('MS_GRAPH_SCOPES', 'openid profile email offline_access Files.Read Sites.Read.All User.Read').split() if scope.strip()]

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', '')
GOOGLE_SCOPES = [scope.strip() for scope in os.getenv('GOOGLE_SCOPES', 'openid email profile https://www.googleapis.com/auth/drive.readonly').split() if scope.strip()]

AGENTMAIL_API_KEY = os.getenv('AGENTMAIL_API_KEY', '')
AGENTMAIL_INBOX_ID = os.getenv('AGENTMAIL_INBOX_ID', '')
AGENTMAIL_BASE_URL = os.getenv('AGENTMAIL_BASE_URL', 'https://api.agentmail.to/v0')

S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', '')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', '')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', '')
S3_BUCKET = os.getenv('S3_BUCKET', '')
S3_REGION = os.getenv('S3_REGION', 'us-east-1')
S3_USE_SSL = os.getenv('S3_USE_SSL', '0') == '1'


USE_S3_STORAGE = bool(S3_ENDPOINT_URL and S3_BUCKET)
if USE_S3_STORAGE:
    AWS_ACCESS_KEY_ID = S3_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = S3_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = S3_BUCKET
    AWS_S3_ENDPOINT_URL = S3_ENDPOINT_URL
    AWS_S3_REGION_NAME = S3_REGION
    AWS_S3_USE_SSL = S3_USE_SSL
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600

SITE_ID = 1
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_ADAPTER = 'control.account_adapter.DocstoreAccountAdapter'
ALLOW_PUBLIC_SIGNUPS = os.getenv('ALLOW_PUBLIC_SIGNUPS', '1') == '1'


CELERY_TASK_DEFAULT_QUEUE = 'docstore'
CELERY_TASK_ROUTES = {
    'ingestion.tasks.ingest_document_task': {'queue': 'docstore'},
}

VOICE_INTEGRATION_ENABLED = os.getenv('VOICE_INTEGRATION_ENABLED', 'false').lower() == 'true'
