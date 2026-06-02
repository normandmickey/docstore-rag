from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0002_spreadsheettransformtemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='spreadsheettransformjob',
            name='ignore_hidden_columns',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='spreadsheettransformjob',
            name='ignore_hidden_rows',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='spreadsheettransformtemplate',
            name='ignore_hidden_columns',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='spreadsheettransformtemplate',
            name='ignore_hidden_rows',
            field=models.BooleanField(default=False),
        ),
    ]
