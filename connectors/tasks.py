import subprocess

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from connectors.models import Connector, ConnectorSyncRun


@shared_task
def run_google_drive_connector_sync(connector_id: int):
    connector = Connector.objects.filter(id=connector_id, provider=Connector.PROVIDER_GOOGLE_DRIVE).first()
    if connector is None:
        return {'ok': False, 'reason': 'connector_not_found'}

    if (connector.config_json or {}).get('folder_id') == 'root':
        return {'ok': False, 'reason': 'root_folder_blocked'}

    recent_running = connector.sync_runs.filter(
        status=ConnectorSyncRun.STATUS_RUNNING,
        started_at__gte=timezone.now() - timezone.timedelta(minutes=30),
    ).exists()
    if recent_running:
        return {'ok': False, 'reason': 'already_running'}

    result = subprocess.run(
        ['.venv/bin/python', 'manage.py', 'sync_google_drive_connector', str(connector.id)],
        cwd=str(settings.BASE_DIR),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    return {
        'ok': result.returncode == 0,
        'returncode': result.returncode,
        'stdout': (result.stdout or '')[:4000],
        'stderr': (result.stderr or '')[:4000],
    }


@shared_task

def schedule_due_connector_syncs():
    now = timezone.now()
    due_connectors = Connector.objects.filter(
        provider=Connector.PROVIDER_GOOGLE_DRIVE,
        status=Connector.STATUS_ACTIVE,
        sync_enabled=True,
        next_sync_at__isnull=False,
        next_sync_at__lte=now,
    )
    scheduled_ids = []
    for connector in due_connectors:
        recent_running = connector.sync_runs.filter(
            status=ConnectorSyncRun.STATUS_RUNNING,
            started_at__gte=now - timezone.timedelta(minutes=30),
        ).exists()
        connector.next_sync_at = now + timezone.timedelta(minutes=max(15, connector.sync_frequency_minutes or 60))
        connector.save(update_fields=['next_sync_at', 'updated_at'])
        if recent_running:
            continue
        run_google_drive_connector_sync.delay(connector.id)
        scheduled_ids.append(connector.id)
    return {'ok': True, 'scheduled_ids': scheduled_ids}
