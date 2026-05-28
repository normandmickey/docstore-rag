from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('control', '0003_apikey'),
        ('documents', '0002_alter_chunk_embedding'),
    ]

    operations = [
        migrations.CreateModel(
            name='Connector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('sharepoint', 'SharePoint')], max_length=40)),
                ('label', models.CharField(max_length=200)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled')], default='active', max_length=20)),
                ('config_json', models.JSONField(blank=True, default=dict)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='connectors', to='control.tenant')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='connectors', to='control.workspace')),
            ],
            options={'ordering': ['tenant__name', 'workspace__name', 'label']},
        ),
        migrations.CreateModel(
            name='ConnectorSyncRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='running', max_length=20)),
                ('summary_json', models.JSONField(blank=True, default=dict)),
                ('error_text', models.TextField(blank=True, default='')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('connector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_runs', to='connectors.connector')),
            ],
            options={'ordering': ['-started_at']},
        ),
        migrations.CreateModel(
            name='ExternalDocumentBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(max_length=255)),
                ('external_path', models.CharField(blank=True, default='', max_length=1000)),
                ('etag', models.CharField(blank=True, default='', max_length=255)),
                ('metadata_json', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('connector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bindings', to='connectors.connector')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='external_bindings', to='documents.document')),
            ],
            options={'ordering': ['connector_id', 'external_path'], 'unique_together': {('connector', 'external_id')}},
        ),
    ]
