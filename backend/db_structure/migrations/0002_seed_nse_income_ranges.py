from django.db import migrations


INCOME_RANGES = (
    ("Below Rs.1 lakh", "1"),
    ("Between Rs.1 lakh to Rs.5 lakhs", "2"),
    ("Between Rs.5 lakhs to Rs.10 lakhs", "3"),
    ("Between Rs.10 lakhs to Rs.25 lakhs", "4"),
    ("Between Rs.25 lakhs to Rs.1 crore", "5"),
    ("More than Rs.1 crore", "6"),
)


def seed_income_ranges(apps, schema_editor):
    income_range = apps.get_model("db_structure", "NseIncomeRangeMaster")
    for label, code in INCOME_RANGES:
        income_range.objects.update_or_create(
            income_range=label,
            defaults={"income_code": code},
        )


def remove_income_ranges(apps, schema_editor):
    income_range = apps.get_model("db_structure", "NseIncomeRangeMaster")
    income_range.objects.filter(
        income_range__in=[label for label, _code in INCOME_RANGES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("db_structure", "0001_initial")]

    operations = [migrations.RunPython(seed_income_ranges, remove_income_ranges)]
