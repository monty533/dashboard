from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0019_remove_missing_cdsl_datetime'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='mode_of_account',
            field=models.CharField(
                blank=True,
                db_column='mode_of_account',
                max_length=50,
                null=True,
            ),
        ),
    ]
