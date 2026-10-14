from django.db import migrations, models


NSDL_ACCOUNT_TYPES = (
    ('current', '11'),
    ('current account', '11'),
    ('saving', '10'),
    ('savings', '10'),
    ('saving account', '10'),
    ('savings account', '10'),
)


def seed_nsdl_account_types(apps, schema_editor):
    alias = schema_editor.connection.alias
    model = apps.get_model('db_structure', 'NsdlAccountTypeMaster')
    for account_type, account_code in NSDL_ACCOUNT_TYPES:
        model.objects.using(alias).update_or_create(
            account_type=account_type,
            defaults={'account_code': account_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0087_ckyc_encrypted_flow'),
    ]

    operations = [
        migrations.CreateModel(
            name='NsdlAccountTypeMaster',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('account_type', models.CharField(db_column='account_type', max_length=50, unique=True)),
                ('account_code', models.CharField(db_column='account_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'nsdl_account_type_master',
                'ordering': ('account_type',),
            },
        ),
        migrations.RunPython(seed_nsdl_account_types, migrations.RunPython.noop),
    ]
