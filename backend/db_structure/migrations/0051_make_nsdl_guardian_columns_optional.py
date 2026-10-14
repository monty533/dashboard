from django.db import migrations, models


NSDL_GUARDIAN_COLUMNS = (
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

NSDL_GUARDIAN_FIELDS = tuple(
    f'nominee{number}{suffix}'
    for number in (1, 2, 3)
    for suffix in NSDL_GUARDIAN_COLUMNS
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


def _clone_field(field, *, optional):
    updated = field.clone()
    updated.set_attributes_from_name(field.name)
    updated.model = field.model
    updated.null = optional
    updated.blank = optional
    updated.default = models.NOT_PROVIDED if optional else ''
    return updated


def make_existing_guardian_columns_optional(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    existing_columns = _existing_nsdl_columns(schema_editor, model)

    for field_name in NSDL_GUARDIAN_FIELDS:
        field = model._meta.get_field(field_name)
        if field.column in existing_columns:
            schema_editor.alter_field(
                model,
                field,
                _clone_field(field, optional=True),
            )


def restore_mandatory_guardian_columns(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    existing_columns = _existing_nsdl_columns(schema_editor, model)
    quote = schema_editor.connection.ops.quote_name
    table = quote(model._meta.db_table)

    for field_name in NSDL_GUARDIAN_FIELDS:
        field = model._meta.get_field(field_name)
        if field.column not in existing_columns:
            continue

        column = quote(field.column)
        schema_editor.execute(
            f'UPDATE {table} SET {column} = %s WHERE {column} IS NULL',
            [''],
        )
        schema_editor.alter_field(
            model,
            field,
            _clone_field(field, optional=False),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0050_add_nsdl_nominee_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    make_existing_guardian_columns_optional,
                    restore_mandatory_guardian_columns,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='nsdl',
                    name=field_name,
                    field=models.CharField(
                        blank=True,
                        db_column=field_name,
                        max_length=50,
                        null=True,
                    ),
                )
                for field_name in NSDL_GUARDIAN_FIELDS
            ],
        ),
    ]
