from django.db import migrations, models


GENDER_CODES = (
    ('male', 'M'),
    ('female', 'F'),
    ('other', 'O'),
)


def seed_gender_codes(apps, schema_editor):
    model = apps.get_model('db_structure', 'BseStarMfGenderMaster')
    for gender, gender_code in GENDER_CODES:
        model.objects.update_or_create(
            gender=gender,
            defaults={'gender_code': gender_code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0078_bse_starmf_lookup_masters'),
    ]

    operations = [
        migrations.CreateModel(
            name='BseStarMfGenderMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gender', models.CharField(db_column='gender', max_length=50, unique=True)),
                ('gender_code', models.CharField(db_column='gender_code', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
            ],
            options={
                'db_table': 'bse_star_mf_gender_master',
                'ordering': ('gender',),
            },
        ),
        migrations.RunPython(seed_gender_codes, migrations.RunPython.noop),
    ]
