from importlib import import_module

from django.db import migrations, models


OLD_NOMINEE_COLUMNS = import_module(
    'db_structure.migrations.0015_userdetails_guardian1_aadhaar_and_more'
).NOMINEE_COLUMNS

RENAMED_COLUMNS = (
    ('Nominee1_name', 'nominee1_name'),
    ('Nominee1_PAN', 'nominee1_pan'),
    ('Nominee1_DOB', 'nominee1_dob'),
    ('Nominee1_relation', 'nominee1_relation'),
    ('Nominee1_address1', 'nominee1_address1'),
    ('Nominee1_address2', 'nominee1_address2'),
    ('Nominee1_city', 'nominee1_city'),
    ('Nominee1_state', 'nominee1_state'),
    ('Nominee1_country', 'nominee1_country'),
    ('Nominee1_pincode', 'nominee1_pincode'),
    ('Nominee1_mobile', 'nominee1_mobile'),
    ('Nominee1_email', 'nominee1_email'),
    ('Nominee2_name', 'nominee2_name'),
    ('Nominee2_PAN', 'nominee2_pan'),
    ('Nominee2_DOB', 'nominee2_dob'),
    ('Nominee2_relation', 'nominee2_relation'),
    ('Nominee2_address1', 'nominee2_address1'),
    ('Nominee2_address2', 'nominee2_address2'),
    ('Nominee2_city', 'nominee2_city'),
    ('Nominee2_state', 'nominee2_state'),
    ('Nominee2_country', 'nominee2_country'),
    ('Nominee2_pincode', 'nominee2_pincode'),
    ('Nominee2_mobile', 'nominee2_mobile'),
    ('Nominee2_email', 'nominee2_email'),
    ('Nominee3_name', 'nominee3_name'),
    ('Nominee3_PAN', 'nominee3_pan'),
    ('Nominee3_DOB', 'nominee3_dob'),
    ('Nominee3_relation', 'nominee3_relation'),
    ('Nominee3_address1', 'nominee3_address1'),
    ('Nominee3_address2', 'nominee3_address2'),
    ('Nominee3_city', 'nominee3_city'),
    ('Nominee3_state', 'nominee3_state'),
    ('Nominee3_country', 'nominee3_country'),
    ('Nominee3_pincode', 'nominee3_pincode'),
    ('Nominee3_mobile', 'nominee3_mobile'),
    ('Nominee3_email', 'nominee3_email'),
)


def _nominee_field(name):
    return models.TextField(
        blank=True,
        db_column=name,
        max_length=255,
        null=True,
    )


def normalize_nominee_columns(apps, schema_editor):
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
    desired_old_names = {old.lower() for old, _ in RENAMED_COLUMNS}
    drop_names = [
        existing[name.lower()]
        for name in OLD_NOMINEE_COLUMNS
        if name.lower() not in desired_old_names and name.lower() in existing
    ]
    if drop_names:
        if connection.vendor == 'sqlite':
            # SQLite supports one DROP COLUMN clause per ALTER TABLE. MySQL
            # accepts the compact multi-clause form used by the legacy
            # migration below.
            for name in drop_names:
                schema_editor.execute(
                    f'ALTER TABLE {table} DROP COLUMN {quote_name(name)}'
                )
        else:
            schema_editor.execute(
                f'ALTER TABLE {table} '
                + ', '.join(f'DROP COLUMN {quote_name(name)}' for name in drop_names)
            )

    with connection.cursor() as cursor:
        descriptions = connection.introspection.get_table_description(
            cursor,
            model._meta.db_table,
        )
    existing = {description.name.lower(): description.name for description in descriptions}

    rename_clauses = []
    for old_name, new_name in RENAMED_COLUMNS:
        actual_name = existing.get(old_name.lower())
        if actual_name and actual_name != new_name:
            if connection.vendor == 'sqlite':
                schema_editor.execute(
                    f'ALTER TABLE {table} RENAME COLUMN '
                    f'{quote_name(actual_name)} TO {quote_name(new_name)}'
                )
            else:
                rename_clauses.append(
                    f'CHANGE COLUMN {quote_name(actual_name)} '
                    f'{quote_name(new_name)} LONGTEXT NULL'
                )
    if rename_clauses:
        schema_editor.execute(
            f'ALTER TABLE {table} ' + ', '.join(rename_clauses)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0015_userdetails_guardian1_aadhaar_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    normalize_nominee_columns,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                *[
                    migrations.RemoveField(
                        model_name='userdetails',
                        name=name,
                    )
                    for name in OLD_NOMINEE_COLUMNS
                ],
                *[
                    migrations.AddField(
                        model_name='userdetails',
                        name=new_name,
                        field=_nominee_field(new_name),
                    )
                    for _, new_name in RENAMED_COLUMNS
                ],
            ],
        ),
    ]
