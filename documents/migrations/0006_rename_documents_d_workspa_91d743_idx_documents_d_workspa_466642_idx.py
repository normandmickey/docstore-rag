from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0005_documentworkspaceassignment'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='documentworkspaceassignment',
            old_name='documents_d_workspa_91d743_idx',
            new_name='documents_d_workspa_466642_idx',
        ),
    ]
