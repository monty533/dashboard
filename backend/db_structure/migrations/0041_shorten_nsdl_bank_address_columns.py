from django.db import migrations, models


NSDL_BANK_ADDRESS_RENAMES = (
    ('bankAddressType', 'addressType'),
    ('bankAddressLine1', 'addressLine1'),
    ('bankAddressLine2', 'addressLine2'),
    ('bankAddressLine3', 'addressLine3'),
    ('bankAddressLine4', 'addressLine4'),
    ('bankAddressZipcode', 'addressZipcode'),
)

NSDL_REQUIRED_FIELDS = frozenset({'addressLine1', 'addressZipcode'})


def _nsdl_field(column_name):
    kwargs = {
        'db_column': column_name,
        'max_length': 50,
    }
    if column_name in NSDL_REQUIRED_FIELDS:
        kwargs['default'] = ''
    else:
        kwargs.update(blank=True, null=True)
    return models.CharField(**kwargs)


class Migration(migrations.Migration):
    dependencies = [
        ('db_structure', '0040_shorten_nsdl_payload_columns'),
    ]

    operations = [
        *(
            migrations.RenameField(
                model_name='nsdl',
                old_name=old_name,
                new_name=new_name,
            )
            for old_name, new_name in NSDL_BANK_ADDRESS_RENAMES
        ),
        *(
            migrations.AlterField(
                model_name='nsdl',
                name=new_name,
                field=_nsdl_field(new_name),
            )
            for _, new_name in NSDL_BANK_ADDRESS_RENAMES
        ),
    ]
