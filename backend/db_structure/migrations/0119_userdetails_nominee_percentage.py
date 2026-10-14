from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0118_userdetails_bank_address_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='nominee1_percentage',
            field=models.CharField(
                blank=True,
                db_column='nominee1_percentage',
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nominee2_percentage',
            field=models.CharField(
                blank=True,
                db_column='nominee2_percentage',
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nominee3_percentage',
            field=models.CharField(
                blank=True,
                db_column='nominee3_percentage',
                max_length=50,
                null=True,
            ),
        ),
    ]
