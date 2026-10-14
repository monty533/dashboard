from django.db import migrations


NSDL_GENDERS = (
    ('male', '1'),
    ('m', '1'),
    ('female', '2'),
    ('f', '2'),
    ('transgender', '3'),
    ('t', '3'),
)

NSDL_COUNTRIES = (
    ('india', '356'),
    ('ind', '356'),
    ('in', '356'),
)

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


def repair_nsdl_lookup_masters(apps, schema_editor):
    alias = schema_editor.connection.alias
    gender_model = apps.get_model('db_structure', 'NsdlGenderMaster')
    country_model = apps.get_model('db_structure', 'NsdlCountryMaster')
    income_model = apps.get_model('db_structure', 'NsdlIncomeRangeMaster')

    for gender, gender_code in NSDL_GENDERS:
        gender_model.objects.using(alias).update_or_create(
            gender=gender,
            defaults={'gender_code': gender_code},
        )
    for country, country_code in NSDL_COUNTRIES:
        country_model.objects.using(alias).update_or_create(
            country=country,
            defaults={'country_code': country_code},
        )
    for income_range, income_code in NSDL_INCOME_RANGES:
        income_model.objects.using(alias).update_or_create(
            income_range=income_range,
            defaults={'income_code': income_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0115_remove_kra_retry_flags'),
    ]

    operations = [
        migrations.RunPython(
            repair_nsdl_lookup_masters,
            migrations.RunPython.noop,
        ),
    ]
