from django.db import migrations


MARITAL_STATUSES = {
    'single': 'S',
    'unmarried': 'S',
    'married': 'M',
    'widow': 'W',
    'widowed': 'W',
    'divorced': 'D',
}


def seed_mcx_marital_statuses(apps, schema_editor):
    marital_status_model = apps.get_model('db_structure', 'McxMaritalStatusMaster')
    for marital_status, marital_code in MARITAL_STATUSES.items():
        marital_status_model.objects.get_or_create(
            marital_status=marital_status,
            defaults={'marital_code': marital_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0071_mcxgendermaster'),
    ]

    operations = [
        migrations.RunPython(seed_mcx_marital_statuses, migrations.RunPython.noop),
    ]
