from django.db import migrations


DEFAULTS = {
    'tax_status': '01',
    'holding_nature': 'SI',
    'client_type': 'P',
    'pms': '',
    'div_pay_mode': '02',
    'communication_mode': 'E',
    'paperless_flag': 'Z',
    'primary_pan_holder_exempt': 'N',
    'primary_holder_kyc_type': 'K',
    'nominee_auth_mode': 'O',
    'registration_type': 'NEW',
}


def seed_master(apps, schema_editor):
    model = apps.get_model('db_structure', 'BseStarMf')
    if not model.objects.exists():
        model.objects.create(**DEFAULTS)


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0075_bse_starmf'),
    ]

    operations = [
        migrations.RunPython(seed_master, migrations.RunPython.noop),
    ]
