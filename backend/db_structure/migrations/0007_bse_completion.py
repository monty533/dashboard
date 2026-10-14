from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('db_structure', '0006_create_bse_income_range_master')]
    operations = [
        migrations.AddField(model_name='userdetails', name='bsecomplete',
                            field=models.CharField(max_length=50, null=True, blank=True)),
        migrations.AddField(model_name='userdetails', name='bse_datetime',
                            field=models.DateTimeField(null=True, blank=True)),
    ]
