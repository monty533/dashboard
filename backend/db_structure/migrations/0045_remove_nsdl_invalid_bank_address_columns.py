from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0044_remove_nsdl_addresscity_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='nsdl',
            name='addresscity',
        ),
        migrations.RemoveField(
            model_name='nsdl',
            name='addresscountrycode',
        ),
        migrations.RemoveField(
            model_name='nsdl',
            name='addressstatecode',
        ),
        migrations.RenameField(
            model_name='nsdl',
            old_name='addresszipcode',
            new_name='zipcode',
        ),
        migrations.AlterField(
            model_name='nsdl',
            name='zipcode',
            field=models.CharField(
                blank=True,
                db_column='zipcode',
                max_length=50,
                null=True,
            ),
        ),
    ]
