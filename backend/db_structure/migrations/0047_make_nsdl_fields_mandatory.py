from django.db import migrations, models


NSDL_FIELDS = (
    'name',
    'shortName',
    'pan',
    'panFlag',
    'grossAnnualIncome',
    'dob',
    'gender',
    'mobile',
    'email',
    'aadhar',
    'ddpiid',
    'eStatement',
    'signature',
    'numOfJointHolders',
    'familyMobileFlag',
    'familyEmailFlag',
    'nominationOption',
    'occupation',
    'fatherOrHusbandName',
    'dpId',
    'clientId',
    'sharePercentEqually',
    'numOfNominees',
    'accountNumber',
    'bankName',
    'accountType',
    'ifsc',
    'micr',
    'addressLine1',
    'addressLine2',
    'addressLine3',
    'addressLine4',
    'addressType',
    'zipcode',
)


def _existing_columns(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        return {
            description.name
            for description in schema_editor.connection.introspection.get_table_description(
                cursor,
                model._meta.db_table,
            )
        }


def _clone_field(field, *, mandatory):
    updated = field.clone()
    updated.set_attributes_from_name(field.name)
    updated.model = field.model
    updated.null = not mandatory
    updated.blank = not mandatory
    updated.default = '' if mandatory else models.NOT_PROVIDED
    return updated


def make_existing_nsdl_fields_mandatory(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    existing_columns = _existing_columns(schema_editor, model)
    quote = schema_editor.connection.ops.quote_name
    table = quote(model._meta.db_table)

    for field_name in NSDL_FIELDS:
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
            _clone_field(field, mandatory=True),
        )


def restore_optional_nsdl_fields(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    existing_columns = _existing_columns(schema_editor, model)

    for field_name in NSDL_FIELDS:
        field = model._meta.get_field(field_name)
        if field.column in existing_columns:
            schema_editor.alter_field(
                model,
                field,
                _clone_field(field, mandatory=False),
            )


def _mandatory_field(field_name):
    return models.CharField(
        db_column=field_name,
        default='',
        max_length=50,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0046_remove_nsdl_communicationtobesend_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    make_existing_nsdl_fields_mandatory,
                    restore_optional_nsdl_fields,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='nsdl',
                    name=field_name,
                    field=_mandatory_field(field_name),
                )
                for field_name in NSDL_FIELDS
            ],
        ),
    ]
