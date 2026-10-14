from django.db import migrations


INCOME_RANGES = (
    ("below 1 lacs", "1"),
    ("1-5 lac", "2"),
    ("5-10 lacs", "3"),
    ("10-25 lacs", "4"),
    ("25-50 lacs", "5"),
    ("50 lacs-1Cr", "5"),
    ("Above 1Cr", "5"),
)

LEGACY_INCOME_RANGES = (
    "Below Rs.1 lakh",
    "Between Rs.1 lakh to Rs.5 lakhs",
    "Between Rs.5 lakhs to Rs.10 lakhs",
    "Between Rs.10 lakhs to Rs.25 lakhs",
    "Between Rs.25 lakhs to Rs.1 crore",
    "More than Rs.1 crore",
)


def seed_requested_income_ranges(apps, schema_editor):
    income_master = apps.get_model("db_structure", "NseIncomeRangeMaster")
    income_master.objects.using(schema_editor.connection.alias).filter(
        income_range__in=LEGACY_INCOME_RANGES,
    ).delete()
    for label, code in INCOME_RANGES:
        income_master.objects.using(schema_editor.connection.alias).update_or_create(
            income_range=label,
            defaults={"income_code": code},
        )


def remove_requested_income_ranges(apps, schema_editor):
    income_master = apps.get_model("db_structure", "NseIncomeRangeMaster")
    income_master.objects.using(schema_editor.connection.alias).filter(
        income_range__in=[label for label, _code in INCOME_RANGES],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("db_structure", "0004_ensure_nse_support")]

    operations = [
        migrations.RunPython(seed_requested_income_ranges, remove_requested_income_ranges),
    ]
