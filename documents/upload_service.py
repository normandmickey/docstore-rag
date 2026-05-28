import hashlib

from django.db import transaction

from ingestion.models import IngestionJob
from ingestion.tasks import ingest_document_task

from .models import Document, DocumentVersion


def _file_sha256(uploaded_file):
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def create_or_reuse_document(*, tenant, workspace, uploaded_file, filename, mime_type='', size_bytes=0, collection='', uploaded_by=None, raw_text=''):
    content_hash = _file_sha256(uploaded_file) if uploaded_file else ''

    exact_duplicate = Document.objects.filter(
        tenant=tenant,
        workspace=workspace,
        content_hash=content_hash,
    ).first() if content_hash else None
    if exact_duplicate:
        latest_version = exact_duplicate.versions.order_by('-version_number', '-id').first()
        latest_job = exact_duplicate.ingestion_jobs.order_by('-created_at').first()
        return {
            'mode': 'duplicate',
            'document': exact_duplicate,
            'version': latest_version,
            'job': latest_job,
            'content_hash': content_hash,
        }

    existing_same_name = Document.objects.filter(
        tenant=tenant,
        workspace=workspace,
        filename=filename,
    ).order_by('-created_at').first()

    with transaction.atomic():
        if existing_same_name:
            document = existing_same_name
            next_version = (document.versions.order_by('-version_number').first().version_number + 1) if document.versions.exists() else 1
            document.collection = collection
            document.mime_type = mime_type or document.mime_type
            document.size_bytes = size_bytes or document.size_bytes
            document.content_hash = content_hash
            document.file = uploaded_file
            document.status = Document.STATUS_PENDING
            document.save(update_fields=['collection', 'mime_type', 'size_bytes', 'content_hash', 'file', 'status', 'updated_at'])
            version = DocumentVersion.objects.create(
                document=document,
                version_number=next_version,
                object_key=document.object_key,
                content_hash=content_hash,
                extraction_metadata_json={'raw_text': raw_text},
            )
            mode = 'versioned'
        else:
            document = Document.objects.create(
                tenant=tenant,
                workspace=workspace,
                collection=collection,
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                object_key=f'{tenant.slug}/{workspace.slug}/{filename}',
                content_hash=content_hash,
                source_type=Document.SOURCE_UPLOAD,
                uploaded_by=uploaded_by,
                file=uploaded_file,
            )
            version = DocumentVersion.objects.create(
                document=document,
                version_number=1,
                object_key=document.object_key,
                content_hash=content_hash,
                extraction_metadata_json={'raw_text': raw_text},
            )
            mode = 'created'

        job = IngestionJob.objects.create(
            tenant=tenant,
            workspace=workspace,
            document=document,
            document_version=version,
            status=IngestionJob.STATUS_QUEUED,
            stage='queued',
        )
        transaction.on_commit(lambda: ingest_document_task.delay(job.id))

    return {
        'mode': mode,
        'document': document,
        'version': version,
        'job': job,
        'content_hash': content_hash,
    }
