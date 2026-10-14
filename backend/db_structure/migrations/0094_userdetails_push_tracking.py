from django.db import migrations, models


def backfill_push_success(apps, schema_editor):
    UserDetails = apps.get_model('db_structure', 'UserDetails')
    UserDetails.objects.filter(bsecomplete='1').update(bse_push=True)
    UserDetails.objects.filter(nsecomplete='1').update(nse_push=True)


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0093_remove_clientapikey_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='bse_push',
            field=models.BooleanField(blank=True, db_column='bse_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bse_push_at',
            field=models.DateTimeField(blank=True, db_column='bse_push_at', null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nse_push',
            field=models.BooleanField(blank=True, db_column='nse_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nse_push_at',
            field=models.DateTimeField(blank=True, db_column='nse_push_at', null=True),
        ),
        migrations.RunPython(backfill_push_success, migrations.RunPython.noop),
    ]
