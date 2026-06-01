from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('connectors', '0003_connector_sync_schedule'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connector',
            name='provider',
            field=models.CharField(choices=[('sharepoint', 'SharePoint'), ('google_drive', 'Google Drive'), ('confluence', 'Confluence')], max_length=40),
        ),
    ]
