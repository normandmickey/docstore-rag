from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingestion', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingestionjob',
            name='extractor',
            field=models.CharField(choices=[('standard', 'Standard'), ('docling', 'Docling')], default='standard', max_length=20),
        ),
    ]
