from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('control', '0004_invitetoken'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProxiWebThread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proxi_web_threads', to='control.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proxi_web_threads', to=settings.AUTH_USER_MODEL)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proxi_web_threads', to='control.workspace')),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
                'indexes': [models.Index(fields=['tenant', 'workspace', 'user'], name='control_pro_tenant__488d2b_idx')],
            },
        ),
        migrations.CreateModel(
            name='ProxiWebMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant')], max_length=20)),
                ('content', models.TextField()),
                ('retrieval_metadata_json', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='control.proxiwebthread')),
            ],
            options={
                'ordering': ['id'],
                'indexes': [models.Index(fields=['thread', 'id'], name='control_pro_thread__a07dff_idx')],
            },
        ),
    ]
