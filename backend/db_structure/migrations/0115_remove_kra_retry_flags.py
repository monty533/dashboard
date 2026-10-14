from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0114_mse_lookup_masters'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userdetails',
            name='kra_data_pushed',
        ),
        migrations.RemoveField(
            model_name='userdetails',
            name='kra_complete_pushed',
        ),
    ]
