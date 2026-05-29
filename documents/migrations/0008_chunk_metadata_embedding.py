from django.db import migrations, models
import pgvector.django.vector


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0007_extractedfact'),
    ]

    operations = [
        migrations.AddField(
            model_name='chunk',
            name='metadata_embedding',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=3072, null=True),
        ),
        migrations.AddField(
            model_name='chunk',
            name='metadata_text',
            field=models.TextField(blank=True, default=''),
        ),
    ]
