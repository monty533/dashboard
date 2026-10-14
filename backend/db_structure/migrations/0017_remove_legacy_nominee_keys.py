from django.db import migrations


LEGACY_NOMINEE_COLUMNS = (
    'nominee_check',
    'nomineeregistrationnumber',
)


def remove_legacy_nominee_columns(apps, schema_editor):
    model = apps.get_model('db_structure', 'UserDetails')
    connection = schema_editor.connection
    quote_name = connection.ops.quote_name
    table = quote_name(model._meta.db_table)

    with connection.cursor() as cursor:
        descriptions = connection.introspection.get_table_description(
            cursor,
            model._meta.db_table,
        )

    existing = {description.name.lower(): description.name for description in descriptions}
    drop_names = [
        existing[name.lower()]
        for name in LEGACY_NOMINEE_COLUMNS
        if name.lower() in existing
    ]
    if drop_names:
        if connection.vendor == 'sqlite':
            for name in drop_names:
                schema_editor.execute(
                    f'ALTER TABLE {table} DROP COLUMN {quote_name(name)}'
                )
        else:
            schema_editor.execute(
                f'ALTER TABLE {table} '
                + ', '.join(f'DROP COLUMN {quote_name(name)}' for name in drop_names)
            )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0016_normalize_nominee_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    remove_legacy_nominee_columns,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='userdetails',
                    name=name,
                )
                for name in LEGACY_NOMINEE_COLUMNS
            ],
        ),
    ]
