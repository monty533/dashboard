from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0095_replace_bse_completion_with_push'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetails',
            name='nse_push',
            field=models.CharField(
                blank=True,
                db_column='nse_push',
                max_length=50,
                null=True,
            ),
        ),
        migrations.RemoveField(
            model_name='userdetails',
            name='nsecomplete',
        ),
        migrations.RemoveField(
            model_name='userdetails',
            name='nse_datetime',
        ),
    ]
