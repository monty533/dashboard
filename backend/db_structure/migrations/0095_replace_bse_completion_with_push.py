from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0094_userdetails_push_tracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetails',
            name='bse_push',
            field=models.CharField(
                blank=True,
                db_column='bse_push',
                max_length=50,
                null=True,
            ),
        ),
        migrations.RemoveField(
            model_name='userdetails',
            name='bsecomplete',
        ),
        migrations.RemoveField(
            model_name='userdetails',
            name='bse_datetime',
        ),
    ]
