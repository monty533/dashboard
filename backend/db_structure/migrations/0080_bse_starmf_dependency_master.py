from django.db import migrations, models


DEPENDENCY_CODES = (
    ('self', 'SE'),
    ('spouse', 'SP'),
    ('child dependent 1', 'DC'),
    ('parent dependent 1', 'DP'),
)


def seed_dependency_codes(apps, schema_editor):
    model = apps.get_model('db_structure', 'BseStarMfDependencyMaster')
    for dependency, dependency_code in DEPENDENCY_CODES:
        model.objects.update_or_create(
            dependency=dependency,
            defaults={'dependency_code': dependency_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0079_bse_starmf_gender_master'),
    ]

    operations = [
        migrations.CreateModel(
            name='BseStarMfDependencyMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dependency', models.CharField(db_column='dependency', max_length=100, unique=True)),
                ('dependency_code', models.CharField(db_column='dependency_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'bse_star_mf_dependency_master',
                'ordering': ('dependency',),
            },
        ),
        migrations.RunPython(seed_dependency_codes, migrations.RunPython.noop),
    ]
