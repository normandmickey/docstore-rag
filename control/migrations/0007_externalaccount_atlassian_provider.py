from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('control', '0006_externalaccount_google_provider'),
    ]

    operations = [
        migrations.AlterField(
            model_name='externalaccount',
            name='provider',
            field=models.CharField(choices=[('microsoft', 'Microsoft'), ('google', 'Google'), ('atlassian', 'Atlassian')], max_length=40),
        ),
    ]
