from django.db import migrations, models


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


def seed_nsdl_gender_country_masters(apps, schema_editor):
    alias = schema_editor.connection.alias
    gender_model = apps.get_model('db_structure', 'NsdlGenderMaster')
    country_model = apps.get_model('db_structure', 'NsdlCountryMaster')

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


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0088_nsdl_account_type_master'),
    ]

    operations = [
        migrations.CreateModel(
            name='NsdlGenderMaster',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('gender', models.CharField(db_column='gender', max_length=50, unique=True)),
                ('gender_code', models.CharField(db_column='gender_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'nsdl_gender_master',
                'ordering': ('gender',),
            },
        ),
        migrations.CreateModel(
            name='NsdlCountryMaster',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('country', models.CharField(db_column='country', max_length=100, unique=True)),
                ('country_code', models.CharField(db_column='country_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'nsdl_country_master',
                'ordering': ('country',),
            },
        ),
        migrations.RunPython(seed_nsdl_gender_country_masters, migrations.RunPython.noop),
    ]
