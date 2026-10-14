from django.db import migrations


ACCOUNT_TYPES = {
    'saving': '10',
    'savings': '10',
    'current': '11',
    'others': '99',
    'other': '99',
}


def seed_mcx_account_types(apps, schema_editor):
    account_type_model = apps.get_model('db_structure', 'McxAccountTypeMaster')
    for account_type, account_code in ACCOUNT_TYPES.items():
        account_type_model.objects.get_or_create(
            account_type=account_type,
            defaults={'account_code': account_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0072_seed_mcx_marital_statuses'),
    ]

    operations = [
        migrations.RunPython(seed_mcx_account_types, migrations.RunPython.noop),
    ]
