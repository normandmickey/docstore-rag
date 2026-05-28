from celery import shared_task
from django.utils import timezone

from documents.models import Chunk, Document
from .models import IngestionJob


def naive_chunks(text, chunk_size=800):
    text = (text or '').strip()
    if not text:
        return []
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 1})
def ingest_document_task(self, ingestion_job_id):
    job = IngestionJob.objects.select_related('document', 'document_version', 'tenant', 'workspace').get(id=ingestion_job_id)
    document = job.document
    version = job.document_version

    job.status = IngestionJob.STATUS_RUNNING
    job.stage = 'extracting'
    job.started_at = timezone.now()
    job.error_text = ''
    job.save(update_fields=['status', 'stage', 'started_at', 'error_text'])

    document.status = Document.STATUS_PROCESSING
    document.save(update_fields=['status', 'updated_at'])

    try:
        extracted_text = ''
        if document.file:
            with document.file.open('rb') as fh:
                raw = fh.read()
            extracted_text = raw.decode('utf-8', errors='ignore')
        else:
            extracted_text = version.extraction_metadata_json.get('raw_text', '')

        chunks = naive_chunks(extracted_text, chunk_size=job.workspace.default_chunk_size or 800)
        Chunk.objects.filter(document_version=version).delete()
        for idx, chunk_text in enumerate(chunks):
            Chunk.objects.create(
                tenant=job.tenant,
                workspace=job.workspace,
                document=document,
                document_version=version,
                chunk_index=idx,
                text=chunk_text,
                token_count=max(1, len(chunk_text) // 4),
                metadata_json={'stub': True},
                embedding=None,
            )

        version.parse_status = 'ready'
        version.extraction_metadata_json = {
            **(version.extraction_metadata_json or {}),
            'raw_text_preview': extracted_text[:500],
            'chunk_count': len(chunks),
        }
        version.save(update_fields=['parse_status', 'extraction_metadata_json'])

        document.status = Document.STATUS_READY
        document.save(update_fields=['status', 'updated_at'])

        job.status = IngestionJob.STATUS_SUCCEEDED
        job.stage = 'done'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'stage', 'finished_at'])
        return {'chunk_count': len(chunks)}
    except Exception as exc:
        job.status = IngestionJob.STATUS_FAILED
        job.stage = 'failed'
        job.error_text = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'stage', 'error_text', 'finished_at'])
        document.status = Document.STATUS_FAILED
        document.save(update_fields=['status', 'updated_at'])
        raise
