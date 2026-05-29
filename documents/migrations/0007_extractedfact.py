from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0006_alter_document_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtractedFact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fact_type', models.CharField(choices=[('list_item', 'List item'), ('policy', 'Policy statement'), ('heading', 'Heading')], default='policy', max_length=32)),
                ('label', models.CharField(blank=True, default='', max_length=255)),
                ('value_text', models.TextField()),
                ('normalized_text', models.TextField(blank=True, default='')),
                ('metadata_json', models.JSONField(blank=True, default=dict)),
                ('confidence', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chunk', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='extracted_facts', to='documents.chunk')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extracted_facts', to='documents.document')),
                ('document_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extracted_facts', to='documents.documentversion')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extracted_facts', to='control.tenant')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extracted_facts', to='control.workspace')),
            ],
            options={
                'ordering': ['document_id', 'id'],
                'indexes': [models.Index(fields=['tenant', 'workspace', 'document'], name='documents_e_tenant__d7f512_idx'), models.Index(fields=['tenant', 'workspace', 'fact_type'], name='documents_e_tenant__238d5f_idx')],
            },
        ),
    ]
