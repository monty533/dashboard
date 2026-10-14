from django.db import migrations


def ensure_bse_credentials(apps, schema_editor):
    model = apps.get_model('db_structure', 'BseCredentials')
    if model._meta.db_table not in schema_editor.connection.introspection.table_names():
        schema_editor.create_model(model)


class Migration(migrations.Migration):
    dependencies = [('db_structure', '0007_bse_completion')]

    operations = [
        migrations.RunPython(ensure_bse_credentials, migrations.RunPython.noop, atomic=False),
    ]
