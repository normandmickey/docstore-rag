import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('docstore_rag')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.task_default_queue = 'docstore'
app.conf.beat_schedule = {
    'schedule-due-connector-syncs-every-5-minutes': {
        'task': 'connectors.tasks.schedule_due_connector_syncs',
        'schedule': crontab(minute='*/5'),
    },
}
