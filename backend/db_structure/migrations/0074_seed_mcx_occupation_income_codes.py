from django.db import migrations


OCCUPATION_CODES = ('01', '02', '03', '04', '05', '06', '07', '08', '09', '99')
INCOME_CODES = ('01', '02', '03', '04', '05')


def seed_mcx_occupation_income_codes(apps, schema_editor):
    occupation_model = apps.get_model('db_structure', 'McxOccupationMaster')
    income_model = apps.get_model('db_structure', 'McxIncomeRangeMaster')

    for code in OCCUPATION_CODES:
        occupation_model.objects.get_or_create(
            occupation_name=code,
            defaults={'occupation_code': code},
        )

    for code in INCOME_CODES:
        income_model.objects.get_or_create(
            income_range=code,
            defaults={'income_code': code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0073_seed_mcx_account_types'),
    ]

    operations = [
        migrations.RunPython(seed_mcx_occupation_income_codes, migrations.RunPython.noop),
    ]
