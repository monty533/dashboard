from django.db import migrations, models


def populate_message_limits(apps, schema_editor):
    KraErrorCode = apps.get_model('db_structure', 'KraErrorCode')
    for row in KraErrorCode.objects.iterator():
        row.message_limit = len(row.message or '')
        row.save(update_fields=['message_limit'])


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0108_kra_error_code_master'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kraerrorcode',
            name='message',
            field=models.CharField(max_length=112, db_column='message'),
        ),
        migrations.AddField(
            model_name='kraerrorcode',
            name='message_limit',
            field=models.PositiveIntegerField(default=0, db_column='message_limit'),
        ),
        migrations.RunPython(populate_message_limits, migrations.RunPython.noop),
    ]
