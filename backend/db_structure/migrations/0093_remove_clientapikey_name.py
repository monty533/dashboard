from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0092_clientapikey'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clientapikey',
            name='name',
        ),
    ]
