from django.db import migrations


def seed_mcx_error_codes(apps, schema_editor):
    McxErrorCode = apps.get_model('db_structure', 'McxErrorCode')

    from db_structure.mcx_constants import ERROR_CODE_MAP

    for code, message in ERROR_CODE_MAP.items():
        McxErrorCode.objects.update_or_create(
            code=str(code),
            defaults={'message': '' if message is None else str(message)},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0066_mcxerrorcode'),
    ]

    operations = [
        migrations.RunPython(seed_mcx_error_codes, migrations.RunPython.noop),
    ]
