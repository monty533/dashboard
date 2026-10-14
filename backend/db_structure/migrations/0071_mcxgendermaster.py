from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0070_alter_mcxerrorcode_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='McxGenderMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gender', models.CharField(max_length=50, unique=True)),
                ('gender_code', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'mcx_gender_master',
                'ordering': ('gender',),
            },
        ),
    ]
