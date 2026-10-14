from django.db import migrations, models


BSE_INCOME_RANGES = (
    ("below 1 lacs", "1"),
    ("1-5 lac", "2"),
    ("5-10 lacs", "3"),
    ("10-25 lacs", "4"),
    ("25-50 lacs", "5"),
    ("50 lacs-1Cr", "5"),
    ("Above 1Cr", "5"),
)


def seed_bse_income_ranges(apps, schema_editor):
    income_master = apps.get_model("db_structure", "BseIncomeRangeMaster")
    manager = income_master.objects.using(schema_editor.connection.alias)
    for income_range, income_code in BSE_INCOME_RANGES:
        manager.update_or_create(
            income_range=income_range,
            defaults={"income_code": income_code},
        )


class Migration(migrations.Migration):
    dependencies = [("db_structure", "0005_seed_requested_income_ranges")]

    operations = [
        migrations.CreateModel(
            name="BseIncomeRangeMaster",
            fields=[
                ("id", models.BigAutoField(db_column="id", primary_key=True, serialize=False)),
                ("income_range", models.CharField(db_column="income_range", max_length=50, unique=True)),
                ("income_code", models.CharField(db_column="income_code", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="created_at")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="updated_at")),
            ],
            options={
                "db_table": "bse_income_range_master",
                "ordering": ("id",),
            },
        ),
        migrations.RunPython(seed_bse_income_ranges, migrations.RunPython.noop),
    ]
