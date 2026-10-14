import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0109_kra_error_code_message_limits'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='mse_push',
            field=models.BooleanField(blank=True, db_column='mse_push', default=False),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='mse_push_at',
            field=models.DateTimeField(blank=True, db_column='mse_push_at', null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='mse_request_no',
            field=models.CharField(blank=True, db_column='mse_request_no', default='', max_length=100),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='mse_in_process',
            field=models.BooleanField(blank=True, db_column='mse_in_process', default=False),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='mse_status',
            field=models.CharField(blank=True, db_column='mse_status', default='', max_length=30),
        ),
        migrations.CreateModel(
            name='MseCredentials',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('environment', models.CharField(default='uat', max_length=10)),
                ('login_id', models.CharField(blank=True, default='', max_length=100)),
                ('password', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='mse_credentials', to='auth.user')),
            ],
            options={'db_table': 'mse_credentials'},
        ),
    ]
