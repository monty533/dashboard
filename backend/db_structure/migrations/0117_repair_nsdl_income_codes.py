from django.db import migrations


NSDL_INCOME_RANGES = (
    ('below 1 lac', '01'),
    ('below 1 lacs', '01'),
    ('1-5 lac', '02'),
    ('1-5 lacs', '02'),
    ('5-10 lac', '03'),
    ('5-10 lacs', '03'),
    ('10-25 lac', '04'),
    ('10-25 lacs', '04'),
    ('25-30 lacs', '05'),
    ('25-50 lacs', '05'),
    ('50 lacs-1cr', '05'),
    ('50 lacs - 1cr', '05'),
    ('above 1cr', '05'),
    ('above 1 crore', '05'),
)


def repair_nsdl_income_codes(apps, schema_editor):
    alias = schema_editor.connection.alias
    model = apps.get_model('db_structure', 'NsdlIncomeRangeMaster')
    for income_range, income_code in NSDL_INCOME_RANGES:
        model.objects.using(alias).update_or_create(
            income_range=income_range,
            defaults={'income_code': income_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0116_repair_nsdl_lookup_masters'),
    ]

    operations = [
        migrations.RunPython(
            repair_nsdl_income_codes,
            migrations.RunPython.noop,
        ),
    ]
