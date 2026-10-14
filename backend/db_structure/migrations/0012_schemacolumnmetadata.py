from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0011_nsdl_integration'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchemaColumnMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('table_name', models.CharField(max_length=255)),
                ('column_name', models.CharField(max_length=255)),
                ('conditional_parameter', models.CharField(blank=True, default='', max_length=100)),
            ],
            options={
                'db_table': 'schema_column_metadata',
                'constraints': [
                    models.UniqueConstraint(
                        fields=('table_name', 'column_name'),
                        name='schema_column_metadata_unique',
                    ),
                ],
            },
        ),
    ]
