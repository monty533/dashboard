import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0028_userdetails_nominee_check'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NsdlCredentials',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('requesterid', models.CharField(max_length=50)),
                ('certificate_file_name', models.CharField(max_length=255)),
                ('private_key_file_password', models.CharField(max_length=255)),
                ('private_key_filename', models.CharField(max_length=255)),
                ('DDPI_ID', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={'db_table': 'nsdl_credentials'},
        ),
    ]
