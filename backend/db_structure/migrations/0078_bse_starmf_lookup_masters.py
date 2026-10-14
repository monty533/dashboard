from django.db import migrations, models


STATE_CODES = (
    ('andaman & nicobar', 'AN'),
    ('andhra pradesh', 'AP'),
    ('arunachal pradesh', 'AR'),
    ('assam', 'AS'),
    ('bihar', 'BH'),
    ('chandigarh', 'CH'),
    ('chhattisgarh', 'CG'),
    ('goa', 'GO'),
    ('gujarat', 'GU'),
    ('haryana', 'HA'),
    ('himachal pradesh', 'HP'),
    ('jammu & kashmir', 'JM'),
    ('jammu and kashmir', 'JM'),
    ('jharkhand', 'JK'),
    ('karnataka', 'KA'),
    ('kerala', 'KE'),
    ('madhya pradesh', 'MP'),
    ('maharashtra', 'MA'),
    ('manipur', 'MN'),
    ('meghalaya', 'ME'),
    ('mizoram', 'MI'),
    ('nagaland', 'NA'),
    ('new delhi', 'ND'),
    ('delhi', 'DL'),
    ('odisha', 'OR'),
    ('orissa', 'OR'),
    ('pondicherry', 'PO'),
    ('puducherry', 'PO'),
    ('punjab', 'PU'),
    ('rajasthan', 'RA'),
    ('sikkim', 'SI'),
    ('telangana', 'TG'),
    ('telengana', 'TG'),
    ('tamil nadu', 'TN'),
    ('tripura', 'TR'),
    ('uttar pradesh', 'UP'),
    ('uttarakhand', 'UC'),
    ('uttaranchal', 'UC'),
    ('west bengal', 'WB'),
    ('dadra and nagar haveli', 'DN'),
    ('daman and diu', 'DD'),
    ('lakshadweep', 'LD'),
    ('others', 'OH'),
)

TAX_STATUSES = (
    ('individual', '01'),
    ('on behalf of minor', '02'),
    ('huf', '03'),
    ('company', '04'),
    ('partnership firm', '06'),
    ('trust', '08'),
    ('others', '10'),
)


def seed_lookup_masters(apps, schema_editor):
    state_model = apps.get_model('db_structure', 'BseStarMfStateCodeMaster')
    tax_model = apps.get_model('db_structure', 'BseStarMfTaxStatusMaster')

    for state_name, state_code in STATE_CODES:
        state_model.objects.update_or_create(
            state_name=state_name,
            defaults={'state_code': state_code},
        )

    for tax_status, tax_code in TAX_STATUSES:
        tax_model.objects.update_or_create(
            tax_status=tax_status,
            defaults={'tax_code': tax_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0077_alter_bsestarmf_aadhar_seeding_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BseStarMfStateCodeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state_name', models.CharField(db_column='state_name', max_length=100, unique=True)),
                ('state_code', models.CharField(db_column='state_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'bse_star_mf_state_code_master',
                'ordering': ('state_name',),
            },
        ),
        migrations.CreateModel(
            name='BseStarMfTaxStatusMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tax_status', models.CharField(db_column='tax_status', max_length=100, unique=True)),
                ('tax_code', models.CharField(db_column='tax_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'bse_star_mf_tax_status_master',
                'ordering': ('tax_status',),
            },
        ),
        migrations.RunPython(seed_lookup_masters, migrations.RunPython.noop),
    ]
