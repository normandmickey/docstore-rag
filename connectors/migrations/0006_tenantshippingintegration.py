from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('control', '0003_externalaccount'),
        ('connectors', '0005_alter_connector_provider'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantShippingIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('fedexsucks', 'FedExSucks')], default='fedexsucks', max_length=40)),
                ('label', models.CharField(default='Shipping Manager', max_length=200)),
                ('base_url', models.URLField(max_length=500)),
                ('api_key', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled')], default='active', max_length=20)),
                ('metadata_json', models.JSONField(blank=True, default=dict)),
                ('last_tested_at', models.DateTimeField(blank=True, null=True)),
                ('last_test_status', models.CharField(blank=True, default='', max_length=20)),
                ('last_test_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shipping_integrations', to='control.tenant')),
            ],
            options={
                'ordering': ['tenant__name', 'label'],
                'unique_together': {('tenant', 'provider')},
            },
        ),
    ]
