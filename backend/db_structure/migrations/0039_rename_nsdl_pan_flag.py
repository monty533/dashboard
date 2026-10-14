from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('db_structure', '0038_nsdloccupationmaster_nsdlrelationmaster'),
    ]

    operations = [
        migrations.RenameField(
            model_name='nsdl',
            old_name='primaryBeneficiaryPanFlag',
            new_name='panFlag',
        ),
        migrations.AlterField(
            model_name='nsdl',
            name='panFlag',
            field=models.CharField(
                db_column='panFlag',
                default='',
                max_length=50,
            ),
        ),
    ]
