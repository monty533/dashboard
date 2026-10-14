from django.db import migrations, models


MODEL_ONLY_FIELDS = (
    'accounttype2', 'accounttype3', 'bankaccountnumber2',
    'bankaccountnumber3', 'bankaddress2', 'bankaddress3', 'bankname2',
    'bankname3', 'branchname2', 'branchname3', 'commodity', 'equity',
    'ifsc2', 'ifsc3', 'isdefault', 'isdefault2', 'isdefault3', 'micr2',
    'micr3',
)

CHAR_FIELD_LENGTHS = {
    'clientcode': 10,
    'name': 50,
    'pan': 10,
    'fathername': 30,
    'mothername': 30,
    'mobile': 10,
    'email': 30,
    'individual_or_jointholder': 10,
    'segment': 100,
    'addressline1': 100,
    'addressline2': 100,
    'addressline3': 100,
    'country': 100,
    'state': 100,
    'city': 100,
    'pincode': 100,
    'modeoftrading': 7,
    'dpid': 16,
    'dptype': 4,
    'uploadpan': 100,
    'uploadsignature': 100,
    'datetime': 100,
    'annual_income': 100,
    'occupation': 100,
    'adhar_address': 100,
    'marital_status': 100,
    'dob': 100,
    'bankname': 100,
    'ifsc': 100,
    'micr': 100,
    'branchname': 100,
    'bankaddress': 100,
    'bankaccountnumber': 100,
    'accounttype': 100,
    'activestatus': 100,
    'adhar_name': 100,
    'adhar_dob': 100,
    'adhar_gender': 100,
    'adhar_fathername': 100,
    'adhar_house': 100,
    'adhar_dist': 100,
    'adhar_state': 100,
    'adhar_country': 100,
    'adhar_image': 100,
    'adhar_file': 100,
    'adhar_pincode': 100,
    'adhar_no': 100,
    'isdppoa': 100,
    'nsecomplete': 100,
    'cdslresponse': 10,
    'networth_date': 10,
    'nse_datetime': 10,
    'segmentactivedate': 15,
    'bsecomplete': 50,
    'bse_datetime': 15,
    'mode_of_account': 10,
}

NULLABLE_CHAR_FIELDS = frozenset({
    'cdslresponse', 'networth_date', 'nse_datetime', 'nsecomplete',
    'segmentactivedate', 'bsecomplete', 'bse_datetime',
})

TEXT_FIELDS = (
    'networth',
    *(
        f'nominee{number}_{suffix}'
        for number in (1, 2, 3)
        for suffix in (
            'name', 'pan', 'dob', 'relation', 'address1', 'address2',
            'city', 'state', 'country', 'pincode', 'mobile', 'email',
        )
    ),
)


def _char_field(name, max_length, nullable=False, unique=False):
    kwargs = {
        'max_length': max_length,
        'blank': True,
    }
    if name != 'bsecomplete':
        kwargs['db_column'] = name
    if nullable:
        kwargs['null'] = True
    else:
        kwargs['default'] = 'individual' if name == 'individual_or_jointholder' else ''
    if unique:
        kwargs['unique'] = True
    return models.CharField(**kwargs)


def _text_field(name):
    return models.TextField(blank=True, null=True, db_column=name)


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0021_alter_cdslupload_status'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # The live MySQL table already has the target shape. Do not issue
            # DROP/ALTER statements against existing production data.
            database_operations=[],
            state_operations=[
                *[
                    migrations.RemoveField(
                        model_name='userdetails',
                        name=name,
                    )
                    for name in MODEL_ONLY_FIELDS
                ],
                *[
                    migrations.AlterField(
                        model_name='userdetails',
                        name=name,
                        field=_char_field(
                            name,
                            length,
                            nullable=name in NULLABLE_CHAR_FIELDS,
                            unique=name == 'clientcode',
                        ),
                    )
                    for name, length in CHAR_FIELD_LENGTHS.items()
                ],
                *[
                    migrations.AlterField(
                        model_name='userdetails',
                        name=name,
                        field=_text_field(name),
                    )
                    for name in TEXT_FIELDS
                ],
            ],
        ),
    ]
