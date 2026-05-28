from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from connectors.graph import SharePointGraphClient
from connectors.models import Connector, ConnectorSyncRun, ExternalDocumentBinding
from documents.upload_service import create_or_reuse_document


SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md', '.html', '.htm'}


class Command(BaseCommand):
    help = 'Sync a SharePoint connector into its workspace using Microsoft Graph.'

    def add_arguments(self, parser):
        parser.add_argument('connector_id', type=int)

    def handle(self, *args, **options):
        connector = Connector.objects.select_related('tenant', 'workspace').filter(
            id=options['connector_id'],
            provider=Connector.PROVIDER_SHAREPOINT,
        ).first()
        if not connector:
            raise CommandError('SharePoint connector not found.')

        drive_id = connector.config_json.get('drive_id')
        folder_item_id = connector.config_json.get('folder_item_id', 'root')
        if not drive_id:
            raise CommandError('Connector config_json must include drive_id.')

        sync_run = ConnectorSyncRun.objects.create(connector=connector, status=ConnectorSyncRun.STATUS_RUNNING)
        client = SharePointGraphClient()
        created = 0
        versioned = 0
        skipped = 0
        failed = 0

        try:
            for item in client.list_children(drive_id=drive_id, item_id=folder_item_id):
                if 'file' not in item:
                    continue
                name = item.get('name', '')
                lower = name.lower()
                if not any(lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    continue
                try:
                    raw = client.download_content(drive_id=drive_id, item_id=item['id'])
                    uploaded = ContentFile(raw, name=name)
                    result = create_or_reuse_document(
                        tenant=connector.tenant,
                        workspace=connector.workspace,
                        uploaded_file=uploaded,
                        filename=name,
                        mime_type=(item.get('file', {}) or {}).get('mimeType', ''),
                        size_bytes=item.get('size', 0) or 0,
                        collection='sharepoint',
                        uploaded_by=None,
                    )
                    ExternalDocumentBinding.objects.update_or_create(
                        connector=connector,
                        external_id=item['id'],
                        defaults={
                            'external_path': item.get('parentReference', {}).get('path', ''),
                            'etag': item.get('eTag', ''),
                            'document': result['document'],
                            'metadata_json': {
                                'web_url': item.get('webUrl', ''),
                                'name': name,
                            },
                        },
                    )
                    if result['mode'] == 'duplicate':
                        skipped += 1
                    elif result['mode'] == 'versioned':
                        versioned += 1
                    else:
                        created += 1
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f'Failed to sync {name}: {exc}')

            connector.last_synced_at = timezone.now()
            connector.save(update_fields=['last_synced_at', 'updated_at'])
            sync_run.status = ConnectorSyncRun.STATUS_SUCCEEDED
            sync_run.summary_json = {
                'created': created,
                'versioned': versioned,
                'skipped': skipped,
                'failed': failed,
            }
            sync_run.finished_at = timezone.now()
            sync_run.save(update_fields=['status', 'summary_json', 'finished_at'])
            self.stdout.write(self.style.SUCCESS(f'SharePoint sync complete: {sync_run.summary_json}'))
        except Exception as exc:
            sync_run.status = ConnectorSyncRun.STATUS_FAILED
            sync_run.error_text = str(exc)
            sync_run.finished_at = timezone.now()
            sync_run.save(update_fields=['status', 'error_text', 'finished_at'])
            raise
