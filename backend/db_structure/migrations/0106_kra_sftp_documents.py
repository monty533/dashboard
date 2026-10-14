from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0105_alter_userdetails_cdsl_push_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='pdf_file_kra',
            field=models.CharField(
                blank=True,
                db_column='pdf_file_kra',
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='aadhar_xml',
            field=models.CharField(
                blank=True,
                db_column='aadhar_xml',
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='kracredentials',
            name='sftp_host',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='kracredentials',
            name='sftp_port',
            field=models.CharField(blank=True, default='22', max_length=10),
        ),
        migrations.AddField(
            model_name='kracredentials',
            name='sftp_username',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='kracredentials',
            name='sftp_password',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='kracredentials',
            name='sftp_base_path',
            field=models.CharField(blank=True, default='.', max_length=255),
        ),
    ]
