from django.db import migrations, models


NSDL_NOMINEE_COLUMNS = (
    'SeqNo',
    'Name',
    'Share',
    'Dob',
    'Minor',
    'RelationWithNominee',
    'MobileNum',
    'EmailId',
    'IdentificationPan',
    'IdentificationAadhar',
    'IdentificationDematAccId',
    'IdentificationSavingBankAccNo',
    'addressLine1',
    'addressLine2',
    'addressLine3',
    'addressLine4',
    'addressType',
    'addresscity',
    'addresscountrycode',
    'addressstatecode',
    'addresszipcode',
    'GuardianFlag',
    'GuardianName',
    'GuardianRelationship',
    'GuardianMobileNum',
    'GuardianEmailId',
    'GuardianIdentificationPan',
    'GuardianIdentificationAadhar',
    'GuardianIdentificationDematAccId',
    'GuardianIdentificationSavingBankAccNo',
    'guardianAddressLine1',
    'guardianAddressLine2',
    'guardianAddressLine3',
    'guardianAddressLine4',
    'guardianAddressType',
    'guardianAddresscity',
    'guardianAddresscountrycode',
    'guardianAddressStatecode',
    'guardianAddresszipcode',
)

NSDL_NOMINEE_FIELDS = tuple(
    f'nominee{number}{suffix}'
    for number in (1, 2, 3)
    for suffix in NSDL_NOMINEE_COLUMNS
)


def _existing_nsdl_columns(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        return {
            description.name
            for description in schema_editor.connection.introspection.get_table_description(
                cursor,
                model._meta.db_table,
            )
        }


def _nsdl_nominee_field(model, field_name):
    field = models.CharField(
        db_column=field_name,
        default='',
        max_length=50,
    )
    field.set_attributes_from_name(field_name)
    field.model = model
    return field


def add_missing_nsdl_nominee_columns(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    existing_columns = _existing_nsdl_columns(schema_editor, model)
    for field_name in NSDL_NOMINEE_FIELDS:
        if field_name not in existing_columns:
            schema_editor.add_field(model, _nsdl_nominee_field(model, field_name))
            existing_columns.add(field_name)


def remove_existing_nsdl_nominee_columns(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    existing_columns = _existing_nsdl_columns(schema_editor, model)
    for field_name in reversed(NSDL_NOMINEE_FIELDS):
        if field_name in existing_columns:
            schema_editor.remove_field(
                model,
                _nsdl_nominee_field(model, field_name),
            )
            existing_columns.remove(field_name)


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0049_add_nsdl_primary_address_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_missing_nsdl_nominee_columns,
                    remove_existing_nsdl_nominee_columns,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='nsdl',
                    name=field_name,
                    field=models.CharField(
                        db_column=field_name,
                        default='',
                        max_length=50,
                    ),
                )
                for field_name in NSDL_NOMINEE_FIELDS
            ],
        ),
    ]
