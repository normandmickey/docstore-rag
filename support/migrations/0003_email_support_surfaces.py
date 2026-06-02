from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('control', '0003_externalaccount'),
        ('support', '0002_alter_supportmessage_kind_supportcall'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportcontact',
            name='email',
            field=models.EmailField(blank=True, db_index=True, default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='supportcontact',
            name='phone_number',
            field=models.CharField(blank=True, db_index=True, default='', max_length=32),
        ),
        migrations.AlterModelOptions(
            name='supportcontact',
            options={'ordering': ['tenant__name', 'email', 'phone_number']},
        ),
        migrations.AlterField(
            model_name='supportmessage',
            name='kind',
            field=models.CharField(choices=[('sms', 'SMS'), ('email', 'Email'), ('call_note', 'Call Note'), ('voicemail', 'Voicemail'), ('system', 'System')], default='sms', max_length=20),
        ),
        migrations.AlterField(
            model_name='supportchannel',
            name='channel_type',
            field=models.CharField(choices=[('sms', 'SMS'), ('voice', 'Voice'), ('both', 'SMS + Voice'), ('email', 'Email')], default='sms', max_length=20),
        ),
        migrations.CreateModel(
            name='TenantEmailIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('agentmail', 'AgentMail')], default='agentmail', max_length=40)),
                ('label', models.CharField(default='Support Email', max_length=200)),
                ('from_name', models.CharField(blank=True, default='', max_length=200)),
                ('from_email', models.EmailField(blank=True, default='', max_length=254)),
                ('inbox_id', models.CharField(blank=True, default='', max_length=255)),
                ('api_key', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled')], default='active', max_length=20)),
                ('auto_reply_enabled', models.BooleanField(default=False)),
                ('metadata_json', models.JSONField(blank=True, default=dict)),
                ('last_tested_at', models.DateTimeField(blank=True, null=True)),
                ('last_test_status', models.CharField(blank=True, default='', max_length=20)),
                ('last_test_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('default_workspace', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tenant_email_integrations', to='control.workspace')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_integrations', to='control.tenant')),
            ],
            options={
                'ordering': ['tenant__name', 'label'],
                'unique_together': {('tenant', 'provider')},
            },
        ),
    ]
