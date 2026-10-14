from django.db import migrations, models


NOMINEE_COLUMNS = tuple(
    f'nominee{number}_{suffix}'
    for number in (1, 2, 3)
    for suffix in (
        'name', 'pan', 'dob', 'relation', 'address1', 'address2', 'city',
        'state', 'country', 'pincode', 'mobile', 'email',
    )
)


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0018_sync_userdetails_model_to_table'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # The legacy database column is already absent. Update only
            # Django's model state so no DROP COLUMN is attempted.
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='userdetails',
                    name='cdsl_datetime',
                ),
                *[
                    migrations.AlterField(
                        model_name='userdetails',
                        name=name,
                        field=models.TextField(
                            db_column=name,
                            max_length=50,
                            null=True,
                            blank=True,
                        ),
                    )
                    for name in NOMINEE_COLUMNS
                ],
            ],
        ),
    ]
