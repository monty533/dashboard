from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('db_structure', '0080_bse_starmf_dependency_master'),
    ]

    operations = [
        migrations.CreateModel(
            name='CkycCredentials',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('environment', models.CharField(default='uat', max_length=10)),
                ('ckyc_base_url', models.CharField(blank=True, default='', max_length=255)),
                ('auth_api_key', models.CharField(blank=True, default='', max_length=255)),
                ('username', models.CharField(blank=True, default='', max_length=100)),
                ('password', models.CharField(blank=True, default='', max_length=255)),
                ('ficode_ckyc', models.CharField(blank=True, default='', max_length=50)),
                ('region_or_branch_code_ckyc', models.CharField(blank=True, default='', max_length=50)),
                ('userid_ckyc', models.CharField(blank=True, default='', max_length=50)),
                ('KYCVerificationName', models.CharField(blank=True, default='', max_length=100)),
                ('KYCVerificationDesignation', models.CharField(blank=True, default='', max_length=100)),
                ('KYCVerificationBranch', models.CharField(blank=True, default='', max_length=100)),
                ('KYCVerificationEMPcode', models.CharField(blank=True, default='', max_length=50)),
                ('OrganisationName', models.CharField(blank=True, default='', max_length=150)),
                ('OrganisationCode', models.CharField(blank=True, default='', max_length=50)),
                ('is_only_generate', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    db_column='user_id',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ckyc_credentials',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'ckyc_credentials',
                'unique_together': {('user', 'environment')},
            },
        ),
    ]
