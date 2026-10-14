from django.db import migrations


def repair_nsdl_columns(apps, schema_editor):
    """Add NSDL columns missing from a partially migrated MySQL table."""
    model = apps.get_model('db_structure', 'Nsdl')
    table = model._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing = {
            column.name.casefold()
            for column in schema_editor.connection.introspection.get_table_description(
                cursor,
                table,
            )
        }

    for field in model._meta.concrete_fields:
        if field.primary_key or field.column.casefold() in existing:
            continue
        field.model = model
        schema_editor.add_field(model, field)
        existing.add(field.column.casefold())


class Migration(migrations.Migration):
    # MySQL cannot roll back ALTER TABLE statements.
    atomic = False

    dependencies = [
        ('db_structure', '0036_nsdl_additionalbenedetailsclientid_and_more'),
    ]

    operations = [
        migrations.RunPython(
            repair_nsdl_columns,
            migrations.RunPython.noop,
        ),
    ]
