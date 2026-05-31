from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('control', '0006_externalaccount_google_provider'),
        ('documents', '0009_chunk_question_embedding'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentWorkspaceAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='workspace_assignments', to='documents.document')),
                ('workspace', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='document_assignments', to='control.workspace')),
            ],
            options={
                'ordering': ['document_id', 'workspace__name'],
                'unique_together': {('document', 'workspace')},
            },
        ),
        migrations.AddIndex(
            model_name='documentworkspaceassignment',
            index=models.Index(fields=['workspace', 'document'], name='documents_d_workspa_91d743_idx'),
        ),
        migrations.RunSQL(
            sql=(
                "INSERT INTO documents_documentworkspaceassignment (document_id, workspace_id, is_primary, created_at) "
                "SELECT id, workspace_id, TRUE, NOW() "
                "FROM documents_document "
                "WHERE workspace_id IS NOT NULL "
                "ON CONFLICT (document_id, workspace_id) DO NOTHING;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
