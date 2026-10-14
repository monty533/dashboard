from django.db import migrations, models


def backfill_segment_flags(apps, schema_editor):
    UserDetails = apps.get_model('db_structure', 'UserDetails')
    segment_groups = {
        'bse_push': ('bse_cash', 'bse_cash_push', 'bse_currency', 'bse_currency_push', 'bse_fo', 'bse_fo_push', 'bse_slbm', 'bse_slbm_push'),
        'nse_push': ('nse_cash', 'nse_cash_push', 'nse_currency', 'nse_currency_push', 'nse_fo', 'nse_fo_push', 'nse_slbm', 'nse_slbm_push'),
    }
    truthy = {'1', 'true', 'yes', 'y', 'on'}

    for client in UserDetails.objects.all().iterator():
        updates = {}
        for overall_field, fields in segment_groups.items():
            if getattr(client, overall_field, None) is not True:
                continue
            for selection_field, flag_field in zip(fields[::2], fields[1::2]):
                selected = str(getattr(client, selection_field, '') or '').strip().casefold() in truthy
                if selected:
                    setattr(client, flag_field, True)
                    updates[flag_field] = True
        if updates:
            client.save(update_fields=list(updates))


class Migration(migrations.Migration):
    dependencies = [
        ('db_structure', '0099_userdetails_transaction_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='bse_cash_push',
            field=models.BooleanField(blank=True, db_column='bse_cash_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bse_currency_push',
            field=models.BooleanField(blank=True, db_column='bse_currency_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bse_fo_push',
            field=models.BooleanField(blank=True, db_column='bse_fo_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bse_slbm_push',
            field=models.BooleanField(blank=True, db_column='bse_slbm_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nse_cash_push',
            field=models.BooleanField(blank=True, db_column='nse_cash_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nse_currency_push',
            field=models.BooleanField(blank=True, db_column='nse_currency_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nse_fo_push',
            field=models.BooleanField(blank=True, db_column='nse_fo_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nse_slbm_push',
            field=models.BooleanField(blank=True, db_column='nse_slbm_push', default=None, null=True),
        ),
        migrations.RunPython(backfill_segment_flags, migrations.RunPython.noop),
    ]
