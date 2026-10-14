from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0106_kra_sftp_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='kra_data_pushed',
            field=models.BooleanField(
                blank=True,
                db_column='kra_data_pushed',
                default=False,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='kra_complete_pushed',
            field=models.BooleanField(
                blank=True,
                db_column='kra_complete_pushed',
                default=False,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='kra_sftp_response',
            field=models.CharField(
                blank=True,
                db_column='kra_sftp_response',
                default='',
                max_length=255,
            ),
        ),
    ]
