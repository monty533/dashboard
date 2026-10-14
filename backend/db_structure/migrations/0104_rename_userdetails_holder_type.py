from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0103_remove_userdetails_cdslresponse_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='userdetails',
            old_name='individual_or_jointholder',
            new_name='account_holder_type',
        ),
        migrations.AlterField(
            model_name='userdetails',
            name='account_holder_type',
            field=models.CharField(
                db_column='account_holder_type',
                default='individual',
                max_length=50,
            ),
        ),
    ]
