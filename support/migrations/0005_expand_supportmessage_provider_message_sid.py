from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0004_alter_supportcontact_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='supportmessage',
            name='provider_message_sid',
            field=models.CharField(blank=True, db_index=True, default='', max_length=255),
        ),
    ]
