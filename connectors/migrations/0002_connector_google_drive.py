from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('connectors', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connector',
            name='provider',
            field=models.CharField(choices=[('sharepoint', 'SharePoint'), ('google_drive', 'Google Drive')], max_length=40),
        ),
    ]
