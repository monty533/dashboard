from django.db import migrations


STATE_CODES = {
    "andaman & nicobar islands": "1",
    "andhra pradesh": "2",
    "arunachal pradesh": "3",
    "assam": "4",
    "bihar": "5",
    "chandigarh": "6",
    "dadra & nagar haveli": "7",
    "dadra and nagar haveli": "7",
    "daman and diu": "8",
    "daman & diu": "8",
    "delhi": "9",
    "goa": "10",
    "gujarat": "11",
    "haryana": "12",
    "himachal pradesh": "13",
    "jammu & kashmir": "14",
    "jammu and kashmir": "14",
    "karnataka": "15",
    "kerala": "16",
    "lakhswadeep": "17",
    "madhya pradesh": "18",
    "maharashtra": "19",
    "manipur": "20",
    "meghalaya": "21",
    "mizoram": "22",
    "nagaland": "23",
    "orissa": "24",
    "odisha": "24",
    "puducherry": "25",
    "pondicherry": "25",
    "punjab": "26",
    "rajasthan": "27",
    "sikkim": "28",
    "tamil nadu": "29",
    "tripura": "30",
    "uttar pradesh": "31",
    "west bengal": "32",
    "chhattisgarh": "33",
    "uttarakhand": "34",
    "uttaranchal": "34",
    "jharkhand": "35",
    "telangana": "37",
    "ladakh": "38",
    "apo": "98",
}


def seed_state_codes(apps, schema_editor):
    state_master = apps.get_model("db_structure", "NseStateCodeMaster")
    for name, code in STATE_CODES.items():
        state_master.objects.using(schema_editor.connection.alias).update_or_create(
            state_name=name,
            defaults={"state_code": code},
        )


class Migration(migrations.Migration):
    dependencies = [("db_structure", "0002_seed_nse_income_ranges")]

    operations = [migrations.RunPython(seed_state_codes, migrations.RunPython.noop)]
