from collections import deque

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from connectors.google_drive import GoogleDriveClient, SUPPORTED_GOOGLE_DRIVE_EXPORT_MIME_TYPES
from connectors.models import Connector, ConnectorSyncRun, ExternalDocumentBinding
from control.models import ExternalAccount
from documents.models import Document
from documents.upload_service import create_or_reuse_document


SUPPORTED_FILE_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md', '.html', '.htm', '.csv'}


class Command(BaseCommand):
    help = 'Sync a Google Drive connector into its workspace using a linked Google account.'

    def add_arguments(self, parser):
        parser.add_argument('connector_id', type=int)

    def handle(self, *args, **options):
        connector = Connector.objects.select_related('tenant', 'workspace').filter(
            id=options['connector_id'],
            provider=Connector.PROVIDER_GOOGLE_DRIVE,
        ).first()
        if not connector:
            raise CommandError('Google Drive connector not found.')

        external_account_id = connector.config_json.get('external_account_id')
        folder_id = connector.config_json.get('folder_id', 'root')
        recursive = bool(connector.config_json.get('recursive', True))
        if not external_account_id:
            raise CommandError('Connector config_json must include external_account_id.')

        account = ExternalAccount.objects.filter(
            id=external_account_id,
            provider=ExternalAccount.PROVIDER_GOOGLE,
        ).first()
        if not account or not account.access_token:
            raise CommandError('Linked Google external account not found or missing access token.')

        sync_run = ConnectorSyncRun.objects.create(connector=connector, status=ConnectorSyncRun.STATUS_RUNNING)
        client = GoogleDriveClient(account.access_token)
        created = 0
        versioned = 0
        skipped = 0
        failed = 0
        visited_folders = set()
        folder_queue = deque([folder_id])
        scanned_folders = 0

        try:
            while folder_queue:
                current_folder_id = folder_queue.popleft()
                if current_folder_id in visited_folders:
                    continue
                visited_folders.add(current_folder_id)
                scanned_folders += 1

                if recursive:
                    try:
                        child_folders = client.list_folders(folder_id=current_folder_id, page_size=100)
                        for folder in child_folders:
                            child_id = folder.get('id')
                            if child_id and child_id not in visited_folders:
                                folder_queue.append(child_id)
                    except Exception as exc:
                        failed += 1
                        self.stderr.write(f'Failed to list child folders for {current_folder_id}: {exc}')

                for item in client.list_folder_files(folder_id=current_folder_id, page_size=100):
                    mime_type = item.get('mimeType', '') or ''
                    name = item.get('name', '') or ''
                    lower = name.lower()
                    if mime_type == 'application/vnd.google-apps.folder':
                        continue
                    if mime_type not in SUPPORTED_GOOGLE_DRIVE_EXPORT_MIME_TYPES and not any(lower.endswith(ext) for ext in SUPPORTED_FILE_EXTENSIONS):
                        continue
                    try:
                        raw, import_mime, import_name = client.download_file_bytes(
                            file_id=item['id'],
                            mime_type=mime_type,
                            filename=name,
                        )
                        uploaded = ContentFile(raw, name=import_name or name or 'google-drive-file')
                        result = create_or_reuse_document(
                            tenant=connector.tenant,
                            workspace=connector.workspace,
                            uploaded_file=uploaded,
                            filename=import_name or name or 'google-drive-file',
                            mime_type=import_mime or mime_type,
                            size_bytes=len(raw),
                            collection='google-drive',
                            uploaded_by=None,
                            source_type=Document.SOURCE_CONNECTOR,
                            source_url=item.get('webViewLink', ''),
                        )
                        ExternalDocumentBinding.objects.update_or_create(
                            connector=connector,
                            external_id=item['id'],
                            defaults={
                                'external_path': current_folder_id,
                                'etag': item.get('md5Checksum', ''),
                                'document': result['document'],
                                'metadata_json': {
                                    'name': name,
                                    'mime_type': mime_type,
                                    'modified_time': item.get('modifiedTime', ''),
                                    'web_url': item.get('webViewLink', ''),
                                    'folder_id': current_folder_id,
                                    'root_folder_id': folder_id,
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

                if not recursive:
                    break

            connector.last_synced_at = timezone.now()
            connector.save(update_fields=['last_synced_at', 'updated_at'])
            sync_run.status = ConnectorSyncRun.STATUS_SUCCEEDED
            sync_run.summary_json = {
                'created': created,
                'versioned': versioned,
                'skipped': skipped,
                'failed': failed,
                'folder_id': folder_id,
                'recursive': recursive,
                'scanned_folders': scanned_folders,
            }
            sync_run.finished_at = timezone.now()
            sync_run.save(update_fields=['status', 'summary_json', 'finished_at'])
            self.stdout.write(self.style.SUCCESS(f'Google Drive sync complete: {sync_run.summary_json}'))
        except Exception as exc:
            sync_run.status = ConnectorSyncRun.STATUS_FAILED
            sync_run.error_text = str(exc)
            sync_run.finished_at = timezone.now()
            sync_run.save(update_fields=['status', 'error_text', 'finished_at'])
            raise
