from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0068_mcx_lookup_masters'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mcxerrorcode',
            name='message',
            field=models.CharField(max_length=156),
        ),
    ]
