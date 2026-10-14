from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0097_replace_bsestarmf_completion_with_push'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetails',
            name='bse_push',
            field=models.BooleanField(blank=True, db_column='bse_push', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='userdetails',
            name='bsestarmf_push',
            field=models.BooleanField(blank=True, db_column='bsestarmf_push', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='userdetails',
            name='nse_push',
            field=models.BooleanField(blank=True, db_column='nse_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nsdl_push',
            field=models.BooleanField(blank=True, db_column='nsdl_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='nsdl_push_at',
            field=models.DateTimeField(blank=True, db_column='nsdl_push_at', null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='mcx_push',
            field=models.BooleanField(blank=True, db_column='mcx_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='mcx_push_at',
            field=models.DateTimeField(blank=True, db_column='mcx_push_at', null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='ckyc_push',
            field=models.BooleanField(blank=True, db_column='ckyc_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='ckyc_push_at',
            field=models.DateTimeField(blank=True, db_column='ckyc_push_at', null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='kra_push',
            field=models.BooleanField(blank=True, db_column='kra_push', default=None, null=True),
        ),
        migrations.AddField(
            model_name='userdetails',
            name='kra_push_at',
            field=models.DateTimeField(blank=True, db_column='kra_push_at', null=True),
        ),
    ]
