from django.db import migrations, models


OCCUPATIONS = (
    ("private sector", "2"),
    ("public sector", "1"),
    ("professional", "5"),
    ("housewife", "8"),
    ("agriculturalist", "6"),
    ("retired", "7"),
    ("government service", "34"),
    ("agriculturist", "6"),
    ("business", "4"),
    ("student", "9"),
)


def seed_occupations(apps, schema_editor):
    occupation_master = apps.get_model("db_structure", "NseOccupationMaster")
    for name, code in OCCUPATIONS:
        occupation_master.objects.using(schema_editor.connection.alias).update_or_create(
            occupation_name=name,
            defaults={"occupation_code": code},
        )


class Migration(migrations.Migration):
    dependencies = [("db_structure", "0023_remove_userdetails_segment_and_more")]

    operations = [
        migrations.CreateModel(
            name="NseOccupationMaster",
            fields=[
                ("id", models.BigAutoField(db_column="id", primary_key=True, serialize=False)),
                ("occupation_name", models.CharField(db_column="occupation_name", max_length=50, unique=True)),
                ("occupation_code", models.CharField(db_column="occupation_code", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="created_at")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="updated_at")),
            ],
            options={
                "db_table": "nse_occupation_master",
                "ordering": ("occupation_name",),
            },
        ),
        migrations.RunPython(seed_occupations, migrations.RunPython.noop),
    ]
