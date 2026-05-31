from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('connectors', '0002_connector_google_drive'),
    ]

    operations = [
        migrations.AddField(
            model_name='connector',
            name='next_sync_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='connector',
            name='sync_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='connector',
            name='sync_frequency_minutes',
            field=models.PositiveIntegerField(default=60),
        ),
    ]
