from django.db import migrations


NSDL_DEFAULT_COLUMNS = (
    'primaryBeneficiaryPanFlag',
    'primaryBeneficiaryEStatement',
    'primaryBeneficiaryPeriodicStatement',
    'primaryBeneficiaryDematAccType',
    'primaryBeneficiaryDematAccSubType',
    'primaryBeneficiaryModeOfOperation',
    'primaryBeneficiaryCommunicationToBeSend',
    'additionalBeneDetailsFamilyMobileFlag',
    'additionalBeneDetailsFamilyEmailFlag',
    'bankDetailsAccountNumber',
    'bankDetailsBankName',
    'bankDetailsAccountType',
    'bankDetailsIfsc',
    'bankDetailsMicr',
    'bankDetailsBankAddressType',
    'bankDetailsBankAddressLine1',
    'bankDetailsBankAddressLine2',
    'bankDetailsBankAddressLine3',
    'bankDetailsBankAddressLine4',
    'bankDetailsBankAddressZipcode',
)


def restore_nsdl_default_columns(apps, schema_editor):
    model = apps.get_model('db_structure', 'Nsdl')
    table = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor,
                table,
            )
        }

    for column_name in NSDL_DEFAULT_COLUMNS:
        if column_name in existing:
            continue
        field = model._meta.get_field(column_name)
        field.model = model
        schema_editor.add_field(model, field)
        existing.add(column_name)


class Migration(migrations.Migration):
    # MySQL cannot roll back ALTER TABLE statements. This migration performs
    # schema changes from RunPython, so it must not run inside a transaction.
    atomic = False

    dependencies = [
        ('db_structure', '0033_remove_nsdl_additionalbenedetailsclientid_and_more'),
    ]

    operations = [
        migrations.RunPython(
            restore_nsdl_default_columns,
            migrations.RunPython.noop,
        ),
    ]
