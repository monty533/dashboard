from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0020_add_mode_of_account'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cdslupload',
            name='status',
            field=models.CharField(
                choices=[
                    ('preparing', 'preparing'),
                    ('prepared', 'prepared'),
                    ('submitting', 'submitting'),
                    ('pending', 'pending'),
                    ('accepted', 'accepted'),
                    ('rejected', 'rejected'),
                    ('failed', 'failed'),
                    ('unknown', 'unknown'),
                ],
                default='preparing',
                max_length=20,
            ),
        ),
    ]
