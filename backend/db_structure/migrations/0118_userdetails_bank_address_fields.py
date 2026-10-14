from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0117_repair_nsdl_income_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='bank_city',
            field=models.CharField(
                blank=True,
                db_column='bank_city',
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bank_state',
            field=models.CharField(
                blank=True,
                db_column='bank_state',
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bank_pincode',
            field=models.CharField(
                blank=True,
                db_column='bank_pincode',
                max_length=50,
                null=True,
            ),
        ),
    ]
