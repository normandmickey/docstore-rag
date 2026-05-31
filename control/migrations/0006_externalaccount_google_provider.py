from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0005_proxiwebthread_proxiwebmessage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='externalaccount',
            name='provider',
            field=models.CharField(choices=[('microsoft', 'Microsoft'), ('google', 'Google')], max_length=40),
        ),
    ]
