from django.db import migrations, models

# Keep this historical migration self-contained. Migration 0030 removes this
# temporary model before migration 0031 creates the current online NSDL table.
NSDL_COLUMNS = ()
NSDL_DEFAULTS = {}
NSDL_FIELD_LENGTHS = {}
NSDL_MANDATORY_COLUMNS = frozenset()
NSDL_STR_COLUMNS = frozenset()


def _nsdl_model_field(column):
    field_type = models.TextField if column in NSDL_STR_COLUMNS else models.CharField
    return field_type(
        db_column=column,
        default=NSDL_DEFAULTS.get(column, ''),
        max_length=NSDL_FIELD_LENGTHS.get(column, 100),
        null=column not in NSDL_MANDATORY_COLUMNS,
        blank=column not in NSDL_MANDATORY_COLUMNS,
    )


NSDL_MODEL_FIELDS = [
    ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
    *[(column, _nsdl_model_field(column)) for column in NSDL_COLUMNS],
]


STATE_CODES = (
    ('ANDAMAN & NICOBAR ISLANDS', '35'),
    ('ANDHRA PRADESH', '28'),
    ('ARUNACHAL PRADESH', '12'),
    ('ASSAM', '18'),
    ('BIHAR', '10'),
    ('CHANDIGARH', '04'),
    ('CHHATTISGARH', '22'),
    ('DADRA & NAGAR HAVELI', '26'),
    ('DAMAN & DIU', '25'),
    ('DELHI', '07'),
    ('GOA', '30'),
    ('GUJARAT', '24'),
    ('HARYANA', '06'),
    ('HIMACHAL PRADESH', '02'),
    ('JAMMU & KASHMIR', '01'),
    ('JHARKHAND', '20'),
    ('KARNATAKA', '29'),
    ('KERALA', '32'),
    ('LADAKH', '38'),
    ('LAKSHADWEEP', '31'),
    ('MADHYA PRADESH', '23'),
    ('MAHARASHTRA', '27'),
    ('MANIPUR', '14'),
    ('MEGHALAYA', '17'),
    ('MIZORAM', '15'),
    ('NAGALAND', '13'),
    ('NEW DELHI', '07'),
    ('ODISHA', '21'),
    ('ORISSA', '21'),
    ('PONDICHERRY', '34'),
    ('PUNJAB', '03'),
    ('RAJASTHAN', '08'),
    ('SIKKIM', '11'),
    ('TAMIL NADU', '33'),
    ('TELANGANA', '36'),
    ('TRIPURA', '16'),
    ('UTTAR PRADESH', '09'),
    ('UTTARANCHAL', '05'),
    ('UTTARAKHAND', '05'),
    ('WEST BENGAL', '19'),
)

INCOME_RANGES = (
    ('below 1 lac', 'UPT1L'),
    ('below 1 lacs', 'UPT1L'),
    ('1-5 lac', '1LT5L'),
    ('1-5 lacs', '1LT5L'),
    ('5-10 lac', '5LTXL'),
    ('5-10 lacs', '5LTXL'),
    ('10-25 lac', 'XLTXXV'),
    ('10-25 lacs', 'XLTXXV'),
    ('25-30 lacs', 'GT24L'),
    ('25-50 lacs', 'GT24L'),
    ('50 lacs-1cr', 'GT24L'),
    ('50 lacs - 1cr', 'GT24L'),
    ('above 1cr', '25T1CR'),
    ('above 1 crore', '25T1CR'),
)


def seed_nsdl_masters(apps, schema_editor):
    alias = schema_editor.connection.alias
    state_model = apps.get_model('db_structure', 'NsdlStateCodeMaster')
    income_model = apps.get_model('db_structure', 'NsdlIncomeRangeMaster')
    nsdl_model = apps.get_model('db_structure', 'Nsdl')

    for state_name, state_code in STATE_CODES:
        state_model.objects.using(alias).update_or_create(
            state_name=state_name,
            defaults={'state_code': state_code},
        )
    for income_range, income_code in INCOME_RANGES:
        income_model.objects.using(alias).update_or_create(
            income_range=income_range,
            defaults={'income_code': income_code},
        )
    if not nsdl_model.objects.using(alias).exists():
        nsdl_model.objects.using(alias).create()


def _nsdl_userdetails_field(name):
    if name == 'nsdl_data_exported':
        field = models.CharField(max_length=50, null=True, blank=True, db_column=name)
    else:
        field = models.DateTimeField(null=True, blank=True, db_column=name)
    field.set_attributes_from_name(name)
    return field


def add_nsdl_userdetails_fields(apps, schema_editor):
    model = apps.get_model('db_structure', 'UserDetails')
    table = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table)
        }
    for name in ('nsdl_data_exported', 'nsdl_data_datetime'):
        field = _nsdl_userdetails_field(name)
        if field.db_column not in existing:
            field.model = model
            schema_editor.add_field(model, field)


def remove_nsdl_userdetails_fields(apps, schema_editor):
    model = apps.get_model('db_structure', 'UserDetails')
    table = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table)
        }
    for name in ('nsdl_data_datetime', 'nsdl_data_exported'):
        field = _nsdl_userdetails_field(name)
        if field.db_column in existing:
            field.model = model
            schema_editor.remove_field(model, field)


class Migration(migrations.Migration):
    dependencies = [('db_structure', '0010_seed_cdsl_masters')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_nsdl_userdetails_fields, remove_nsdl_userdetails_fields),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='userdetails',
                    name='nsdl_data_exported',
                    field=models.CharField(db_column='nsdl_data_exported', max_length=50, null=True, blank=True),
                ),
                migrations.AddField(
                    model_name='userdetails',
                    name='nsdl_data_datetime',
                    field=models.DateTimeField(null=True, blank=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Nsdl',
            fields=NSDL_MODEL_FIELDS,
            options={'db_table': 'nsdl'},
        ),
        migrations.CreateModel(
            name='NsdlStateCodeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state_name', models.CharField(db_column='state_name', max_length=50, unique=True)),
                ('state_code', models.CharField(db_column='state_code', max_length=6)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={'db_table': 'nsdl_state_code_master', 'ordering': ('state_name',)},
        ),
        migrations.CreateModel(
            name='NsdlIncomeRangeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('income_range', models.CharField(db_column='income_range', max_length=50, unique=True)),
                ('income_code', models.CharField(db_column='income_code', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={'db_table': 'nsdl_income_range_master', 'ordering': ('id',)},
        ),
        migrations.RunPython(seed_nsdl_masters, migrations.RunPython.noop),
    ]
