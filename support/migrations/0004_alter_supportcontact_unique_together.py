from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0003_email_support_surfaces'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='supportcontact',
            unique_together=set(),
        ),
    ]
