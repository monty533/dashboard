from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0067_seed_mcx_error_codes'),
    ]

    operations = [
        migrations.CreateModel(
            name='McxMaritalStatusMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('marital_status', models.CharField(max_length=50, unique=True)),
                ('marital_code', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'mcx_marital_status_master',
                'ordering': ('marital_status',),
            },
        ),
        migrations.CreateModel(
            name='McxIncomeRangeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('income_range', models.CharField(max_length=50, unique=True)),
                ('income_code', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'mcx_income_range_master',
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='McxOccupationMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occupation_name', models.CharField(max_length=50, unique=True)),
                ('occupation_code', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'mcx_occupation_master',
                'ordering': ('occupation_name',),
            },
        ),
        migrations.CreateModel(
            name='McxAccountTypeMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_type', models.CharField(max_length=50, unique=True)),
                ('account_code', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'mcx_account_type_master',
                'ordering': ('account_type',),
            },
        ),
    ]
