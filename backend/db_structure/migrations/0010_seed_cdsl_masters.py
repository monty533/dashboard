"""CDSL UDiFF V3.0.1.1 values; income labels match the existing user data."""
from django.db import migrations


STATES = (('JAMMU AND KASHMIR', '01'), ('HIMACHAL PRADESH', '02'), ('PUNJAB', '03'), ('CHANDIGARH', '04'), ('UTTARAKHAND', '05'), ('HARYANA', '06'), ('DELHI', '07'), ('RAJASTHAN', '08'), ('UTTAR PRADESH', '09'), ('BIHAR', '10'), ('SIKKIM', '11'), ('ARUNACHAL PRADESH', '12'), ('NAGALAND', '13'), ('MANIPUR', '14'), ('MIZORAM', '15'), ('TRIPURA', '16'), ('MEGHALAYA', '17'), ('ASSAM', '18'), ('WEST BENGAL', '19'), ('JHARKHAND', '20'), ('ODISHA', '21'), ('CHHATTISGARH', '22'), ('MADHYA PRADESH', '23'), ('GUJARAT', '24'), ('DAMAN AND DIU', '25'), ('DADRA-NGR-HVELI-DAMAN-DIU', '26'), ('MAHARASHTRA', '27'), ('ANDHRA PRADESH - BEFORE DIVISION', '28'), ('KARNATAKA', '29'), ('GOA', '30'), ('LAKSHADWEEP', '31'), ('KERALA', '32'), ('TAMIL NADU', '33'), ('PUDUCHERRY', '34'), ('ANDAMAN & NICOBAR ISLANDS', '35'), ('TELANGANA', '36'), ('ANDHRA PRADESH', '37'), ('LADAKH', '38'), ('ARMY POSTAL SERVICE', '99'))
INCOMES = (('below 1 lacs', 'UPT1L'), ('below 1 lac', 'UPT1L'), ('1-5 lac', '1LT5L'), ('5-10 lacs', '5LTXL'), ('10-25 lacs', 'XLTXXV'), ('25-30 lacs', 'GT24L'), ('25-50 lacs', 'GT24L'), ('50 lacs-1Cr', 'GT24L'), ('Above 1Cr', 'GT24L'))


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    for model_name, name_field, code_field, rows in (
        ('CdslStateCodeMaster', 'state_name', 'state_code', STATES),
        ('CdslIncomeRangeMaster', 'income_range', 'income_code', INCOMES),
    ):
        manager = apps.get_model('db_structure', model_name).objects.using(alias)
        for name, code in rows:
            manager.get_or_create(**{name_field: name}, defaults={code_field: code})
    master = apps.get_model('db_structure', 'Cdsl').objects.using(alias)
    if not master.exists():
        master.create()


class Migration(migrations.Migration):
    dependencies = [('db_structure', '0009_cdsl_integration')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
