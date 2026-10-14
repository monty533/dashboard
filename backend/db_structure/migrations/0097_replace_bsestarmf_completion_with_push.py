from django.db import migrations, models


def backfill_bsestarmf_push(apps, schema_editor):
    UserDetails = apps.get_model('db_structure', 'UserDetails')
    UserDetails.objects.filter(bsestarmfcomplete='1').update(bsestarmf_push='1')


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0096_replace_nse_completion_with_push'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='bsestarmf_push',
            field=models.CharField(
                blank=True,
                db_column='bsestarmf_push',
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bsestarmf_push_at',
            field=models.DateTimeField(
                blank=True,
                db_column='bsestarmf_push_at',
                null=True,
            ),
        ),
        migrations.RunPython(backfill_bsestarmf_push, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='userdetails',
            name='bsestarmfcomplete',
        ),
        migrations.RemoveField(
            model_name='userdetails',
            name='bsestarmf_datetime',
        ),
    ]
