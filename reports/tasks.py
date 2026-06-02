from __future__ import annotations

from django.core.files.base import ContentFile
from django.utils import timezone
from celery import shared_task

from .models import SpreadsheetTransformJob
from .spreadsheet_transform import export_transform_csv, export_transform_xlsx


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 1})
def build_spreadsheet_transform_export(self, job_id: int):
    job = SpreadsheetTransformJob.objects.get(id=job_id)
    job.status = SpreadsheetTransformJob.STATUS_RUNNING
    job.started_at = timezone.now()
    job.error_text = ''
    job.save(update_fields=['status', 'started_at', 'error_text'])

    try:
        headers = list(job.headers_json or [])
        rows = list(job.rows_json or [])
        if job.export_format == SpreadsheetTransformJob.EXPORT_CSV:
            payload = export_transform_csv(headers, rows)
            filename = f'spreadsheet-transform-{job.id}.csv'
        else:
            payload = export_transform_xlsx(headers, rows)
            filename = f'spreadsheet-transform-{job.id}.xlsx'

        job.output_file.save(filename, ContentFile(payload), save=False)
        job.status = SpreadsheetTransformJob.STATUS_SUCCEEDED
        job.finished_at = timezone.now()
        job.save(update_fields=['output_file', 'status', 'finished_at'])
    except Exception as exc:
        job.status = SpreadsheetTransformJob.STATUS_FAILED
        job.error_text = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error_text', 'finished_at'])
        raise
