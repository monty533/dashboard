from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0086_kragendermaster_kramaritalstatusmaster_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ckyccredentials',
            name='verify_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='ckyccredentials',
            name='download_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='ckyccredentials',
            name='verify_otp_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='ckyccredentials',
            name='fi_private_key_path',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='ckyccredentials',
            name='fi_public_key_path',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='ckyccredentials',
            name='cersai_public_key_path',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.CreateModel(
            name='CkycTransaction',
            fields=[
                ('id', models.BigAutoField(db_column='id', primary_key=True, serialize=False)),
                ('environment', models.CharField(default='uat', max_length=10)),
                ('pan', models.CharField(blank=True, default='', max_length=50)),
                ('reference_id', models.CharField(blank=True, default='', max_length=50)),
                ('request_id', models.CharField(blank=True, default='', max_length=50)),
                ('auth_factor', models.CharField(blank=True, default='', max_length=50)),
                ('status', models.CharField(blank=True, default='', max_length=30)),
                ('response_data', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(
                    db_column='client_id',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ckyc_transactions',
                    to='db_structure.userdetails',
                )),
            ],
            options={
                'db_table': 'ckyc_transactions',
                'ordering': ('-id',),
            },
        ),
    ]
