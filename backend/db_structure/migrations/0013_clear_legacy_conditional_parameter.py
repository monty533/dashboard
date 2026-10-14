from django.db import migrations


def clear_legacy_conditional_parameter(apps, schema_editor):
    metadata = apps.get_model('db_structure', 'SchemaColumnMetadata')
    metadata.objects.filter(
        conditional_parameter='individual_or_jointholder',
    ).update(conditional_parameter='')


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0012_schemacolumnmetadata'),
    ]

    operations = [
        migrations.RunPython(clear_legacy_conditional_parameter, migrations.RunPython.noop),
    ]
