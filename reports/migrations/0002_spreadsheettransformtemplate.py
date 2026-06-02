from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('control', '0008_alter_externalaccount_provider'),
        ('reports', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SpreadsheetTransformTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('visibility', models.CharField(choices=[('private', 'Private'), ('workspace', 'Workspace'), ('tenant', 'Tenant')], default='private', max_length=20)),
                ('source_headers_json', models.JSONField(blank=True, default=list)),
                ('output_plan_json', models.JSONField(blank=True, default=list)),
                ('column_plan_json', models.JSONField(blank=True, default=list)),
                ('transform_request', models.TextField(blank=True, default='')),
                ('export_format', models.CharField(choices=[('xlsx', 'XLSX'), ('csv', 'CSV')], default='xlsx', max_length=10)),
                ('strict_sanitization', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='spreadsheet_transform_templates', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='spreadsheet_transform_templates', to='control.tenant')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='spreadsheet_transform_templates', to='control.workspace')),
            ],
            options={
                'ordering': ['-updated_at', '-created_at'],
                'indexes': [models.Index(fields=['tenant', 'workspace', 'visibility'], name='reports_spr_tenant__8496a6_idx')],
            },
        ),
    ]
