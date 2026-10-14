from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0098_add_non_cdsl_push_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='transaction_type',
            field=models.CharField(
                db_column='transaction_type',
                default='account_opening',
                max_length=50,
            ),
        ),
    ]
