from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0074_seed_mcx_occupation_income_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='bsestarmf_datetime',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='bsestarmfcomplete',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.CreateModel(
            name='BseStarMf',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('tax_status', models.CharField(db_column='tax_status', default='01', max_length=2)),
                ('holding_nature', models.CharField(db_column='holding_nature', default='SI', max_length=2)),
                ('client_type', models.CharField(db_column='client_type', default='P', max_length=1)),
                ('pms', models.CharField(blank=True, db_column='pms', max_length=1, null=True)),
                ('div_pay_mode', models.CharField(db_column='div_pay_mode', default='02', max_length=2)),
                ('communication_mode', models.CharField(db_column='communication_mode', default='E', max_length=1)),
                ('foreign_address_1', models.CharField(blank=True, db_column='foreign_address_1', max_length=40, null=True)),
                ('foreign_address_2', models.CharField(blank=True, db_column='foreign_address_2', max_length=40, null=True)),
                ('foreign_address_3', models.CharField(blank=True, db_column='foreign_address_3', max_length=40, null=True)),
                ('foreign_city', models.CharField(blank=True, db_column='foreign_city', max_length=35, null=True)),
                ('foreign_pincode', models.CharField(blank=True, db_column='foreign_pincode', max_length=10, null=True)),
                ('foreign_state', models.CharField(blank=True, db_column='foreign_state', max_length=35, null=True)),
                ('foreign_country', models.CharField(blank=True, db_column='foreign_country', max_length=3, null=True)),
                ('paperless_flag', models.CharField(db_column='paperless_flag', default='Z', max_length=1)),
                ('aadhar_seeding_status', models.CharField(blank=True, db_column='aadhar_seeding_status', max_length=1, null=True)),
                ('mapin_id', models.CharField(blank=True, db_column='mapin_id', max_length=20, null=True)),
                ('lei_no', models.CharField(blank=True, db_column='lei_no', max_length=20, null=True)),
                ('lei_validity', models.CharField(blank=True, db_column='lei_validity', max_length=20, null=True)),
                ('primary_pan_holder_exempt', models.CharField(db_column='primary_pan_holder_exempt', default='N', max_length=1)),
                ('second_pan_holder_exempt', models.CharField(blank=True, db_column='second_pan_holder_exempt', max_length=1, null=True)),
                ('third_pan_holder_exempt', models.CharField(blank=True, db_column='third_pan_holder_exempt', max_length=1, null=True)),
                ('guardian_pan_holder_exempt', models.CharField(blank=True, db_column='guardian_pan_holder_exempt', max_length=1, null=True)),
                ('primary_pan_holder_exempt_category', models.CharField(blank=True, db_column='primary_pan_holder_exempt_category', max_length=2, null=True)),
                ('second_pan_holder_exempt_category', models.CharField(blank=True, db_column='second_pan_holder_exempt_category', max_length=2, null=True)),
                ('third_pan_holder_exempt_category', models.CharField(blank=True, db_column='third_pan_holder_exempt_category', max_length=2, null=True)),
                ('guardian_pan_holder_exempt_category', models.CharField(blank=True, db_column='guardian_pan_holder_exempt_category', max_length=2, null=True)),
                ('primary_holder_kyc_type', models.CharField(db_column='primary_holder_kyc_type', default='K', max_length=1)),
                ('primary_holder_ckyc_number', models.CharField(blank=True, db_column='primary_holder_ckyc_number', max_length=20, null=True)),
                ('second_holder_kyc_type', models.CharField(blank=True, db_column='second_holder_kyc_type', max_length=1, null=True)),
                ('second_holder_ckyc_number', models.CharField(blank=True, db_column='second_holder_ckyc_number', max_length=20, null=True)),
                ('third_holder_kyc_type', models.CharField(blank=True, db_column='third_holder_kyc_type', max_length=1, null=True)),
                ('third_holder_ckyc_number', models.CharField(blank=True, db_column='third_holder_ckyc_number', max_length=20, null=True)),
                ('guardian_holder_kyc_type', models.CharField(blank=True, db_column='guardian_holder_kyc_type', max_length=1, null=True)),
                ('guardian_holder_ckyc_number', models.CharField(blank=True, db_column='guardian_holder_ckyc_number', max_length=20, null=True)),
                ('primary_holder_kra_exempt_ref_number', models.CharField(blank=True, db_column='primary_holder_kra_exempt_ref_number', max_length=20, null=True)),
                ('second_holder_kra_exempt_ref_number', models.CharField(blank=True, db_column='second_holder_kra_exempt_ref_number', max_length=20, null=True)),
                ('third_holder_kra_exempt_ref_number', models.CharField(blank=True, db_column='third_holder_kra_exempt_ref_number', max_length=20, null=True)),
                ('guardian_holder_kra_exempt_ref_number', models.CharField(blank=True, db_column='guardian_holder_kra_exempt_ref_number', max_length=20, null=True)),
                ('mobile_declaration_flag', models.CharField(blank=True, db_column='mobile_declaration_flag', max_length=2, null=True)),
                ('email_declaration_flag', models.CharField(blank=True, db_column='email_declaration_flag', max_length=2, null=True)),
                ('guardian_relationship', models.CharField(blank=True, db_column='guardian_relationship', max_length=40, null=True)),
                ('nominee_auth_mode', models.CharField(db_column='nominee_auth_mode', default='O', max_length=1)),
                ('registration_type', models.CharField(db_column='registration_type', default='NEW', max_length=10)),
                ('filler1', models.CharField(blank=True, db_column='filler1', max_length=10, null=True)),
                ('filler2', models.CharField(blank=True, db_column='filler2', max_length=10, null=True)),
                ('filler3', models.CharField(blank=True, db_column='filler3', max_length=10, null=True)),
            ],
            options={'db_table': 'bse_star_mf'},
        ),
        migrations.CreateModel(
            name='BseStarMfCredentials',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('environment', models.CharField(default='uat', max_length=10)),
                ('MemberId', models.CharField(blank=True, default='', max_length=50)),
                ('UserId', models.CharField(blank=True, default='', max_length=50)),
                ('Password', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
                ('user', models.ForeignKey(blank=True, db_column='user_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bse_star_mf_credentials', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'bse_star_mf_credentials',
                'unique_together': {('user', 'environment')},
            },
        ),
    ]
