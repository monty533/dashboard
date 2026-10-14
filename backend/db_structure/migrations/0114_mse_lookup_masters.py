from django.db import migrations, models


MSE_STATE_CODES = (
    ('ANDAMAN & NICOBAR ISLANDS', '1'),
    ('ANDAMAN AND NICOBAR ISLANDS', '1'),
    ('ANDHRA PRADESH', '2'), ('AP', '2'),
    ('ARUNACHAL PRADESH', '3'), ('AR', '3'),
    ('ASSAM', '4'), ('AS', '4'), ('BIHAR', '5'), ('BR', '5'),
    ('CHANDIGARH', '6'), ('CH', '6'),
    ('DADRA & NAGAR HAVELI', '7'), ('DADRA AND NAGAR HAVELI', '7'), ('DN', '7'),
    ('DAMAN & DIU', '8'), ('DAMAN AND DIU', '8'), ('DD', '8'),
    ('DELHI', '9'), ('DL', '9'), ('NEW DELHI', '9'),
    ('GOA', '10'), ('GA', '10'), ('GUJARAT', '11'), ('GJ', '11'),
    ('HARYANA', '12'), ('HR', '12'), ('HIMACHAL PRADESH', '13'), ('HP', '13'),
    ('JAMMU & KASHMIR', '14'), ('JAMMU AND KASHMIR', '14'), ('JK', '14'),
    ('KARNATAKA', '15'), ('KA', '15'), ('KERALA', '16'), ('KL', '16'),
    ('LAKSHADWEEP', '17'), ('LD', '17'), ('MADHYA PRADESH', '18'), ('MP', '18'),
    ('MAHARASHTRA', '19'), ('MH', '19'), ('MANIPUR', '20'), ('MN', '20'),
    ('MEGHALAYA', '21'), ('ML', '21'), ('MIZORAM', '22'), ('MZ', '22'),
    ('NAGALAND', '23'), ('NL', '23'), ('ORISSA', '24'), ('ODISHA', '24'),
    ('OR', '24'), ('OD', '24'), ('PONDICHERRY', '25'), ('PUDUCHERRY', '25'),
    ('PY', '25'), ('PUNJAB', '26'), ('PB', '26'), ('RAJASTHAN', '27'), ('RJ', '27'),
    ('SIKKIM', '28'), ('SK', '28'), ('TAMIL NADU', '29'), ('TN', '29'),
    ('TRIPURA', '30'), ('TR', '30'), ('UTTAR PRADESH', '31'), ('UP', '31'),
    ('WEST BENGAL', '32'), ('WB', '32'), ('CHHATTISGARH', '33'), ('CG', '33'),
    ('UTTARAKHAND', '34'), ('UK', '34'), ('UTTARANCHAL', '34'),
    ('JHARKHAND', '35'), ('JH', '35'), ('TELANGANA', '37'), ('TS', '37'),
    ('LADAKH', '38'), ('LA', '38'), ('OTHERS', '99'),
)
MSE_OCCUPATION_CODES = (
    ('PUBLIC SECTOR', '1'), ('PRIVATE SECTOR', '2'),
    ('GOVERNMENT SERVICE', '3'), ('BUSINESS', '4'), ('PROFESSIONAL', '5'),
    ('AGRICULTURIST', '6'), ('RETIRED', '7'), ('HOUSEWIFE', '8'),
    ('STUDENT', '9'), ('OTHER', '99'), ('OTHERS', '99'),
)
MSE_INCOME_CODES = (
    ('BELOW 1 LAC', '1'), ('1-5 LAC', '2'), ('5-10 LAC', '3'),
    ('10-25 LAC', '4'), ('MORE THAN 25 LAC', '5'), ('25-1 CRORE', '5'),
    ('ABOVE 25 LAC', '5'), ('> 1 CRORE', '6'), ('25-50 LACS', '5'),
    ('50 LACS-1 CRORE', '5'), ('ABOVE 1 CRORE', '6'),
)
MSE_ACCOUNT_TYPE_CODES = (
    ('SAVING ACCOUNT', '10'), ('SAVINGS ACCOUNT', '10'), ('SAVING', '10'),
    ('CURRENT ACCOUNT', '11'), ('CURRENT', '11'), ('OTHERS', '99'),
    ('OTHER', '99'),
)


def _seed_mse_masters(apps, schema_editor):
    State = apps.get_model('db_structure', 'MseStateCodeMaster')
    Occupation = apps.get_model('db_structure', 'MseOccupationMaster')
    Income = apps.get_model('db_structure', 'MseIncomeRangeMaster')
    AccountType = apps.get_model('db_structure', 'MseAccountTypeMaster')

    State.objects.bulk_create(
        [State(state_name=name, state_code=code) for name, code in MSE_STATE_CODES],
        ignore_conflicts=True,
    )
    Occupation.objects.bulk_create(
        [Occupation(occupation_name=name, occupation_code=code) for name, code in MSE_OCCUPATION_CODES],
        ignore_conflicts=True,
    )
    Income.objects.bulk_create(
        [Income(income_range=name, income_code=code) for name, code in MSE_INCOME_CODES],
        ignore_conflicts=True,
    )
    AccountType.objects.bulk_create(
        [AccountType(account_type=name, account_code=code) for name, code in MSE_ACCOUNT_TYPE_CODES],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0114_remove_ckyccredentials_is_only_generate'),
    ]

    operations = [
        migrations.CreateModel(
            name='MseStateCodeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state_name', models.CharField(max_length=100, unique=True)),
                ('state_code', models.CharField(max_length=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'mse_state_code_master', 'ordering': ('state_name',)},
        ),
        migrations.CreateModel(
            name='MseOccupationMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occupation_name', models.CharField(max_length=50, unique=True)),
                ('occupation_code', models.CharField(max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'mse_occupation_master', 'ordering': ('occupation_name',)},
        ),
        migrations.CreateModel(
            name='MseIncomeRangeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('income_range', models.CharField(max_length=50, unique=True)),
                ('income_code', models.CharField(max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'mse_income_range_master', 'ordering': ('income_range',)},
        ),
        migrations.CreateModel(
            name='MseAccountTypeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_type', models.CharField(max_length=50, unique=True)),
                ('account_code', models.CharField(max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'mse_account_type_master', 'ordering': ('account_type',)},
        ),
        migrations.RunPython(_seed_mse_masters, migrations.RunPython.noop),
    ]
