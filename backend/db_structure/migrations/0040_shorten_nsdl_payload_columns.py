from django.db import migrations, models


NSDL_FIELD_RENAMES = (
    ('primaryBeneficiaryName', 'name'),
    ('primaryBeneficiaryShortName', 'shortName'),
    ('primaryBeneficiaryPan', 'pan'),
    ('primaryBeneficiaryGrossAnnualIncome', 'grossAnnualIncome'),
    ('primaryBeneficiaryDob', 'dob'),
    ('primaryBeneficiaryGender', 'gender'),
    ('primaryBeneficiaryMobile', 'mobile'),
    ('primaryBeneficiaryEmail', 'email'),
    ('primaryBeneficiaryAadhar', 'aadhar'),
    ('primaryBeneficiaryDdpiid', 'ddpiid'),
    ('primaryBeneficiaryEStatement', 'eStatement'),
    ('primaryBeneficiaryPeriodicStatement', 'periodicStatement'),
    ('primaryBeneficiaryDematAccType', 'dematAccType'),
    ('primaryBeneficiaryDematAccSubType', 'dematAccSubType'),
    ('primaryBeneficiaryModeOfOperation', 'modeOfOperation'),
    ('primaryBeneficiaryCommunicationToBeSend', 'communicationToBeSend'),
    ('primaryBeneficiarySignature', 'signature'),
    ('primaryBeneficiaryCoresAddressLine1', 'coresAddressLine1'),
    ('primaryBeneficiaryCoresAddressLine2', 'coresAddressLine2'),
    ('primaryBeneficiaryCoresAddressLine3', 'coresAddressLine3'),
    ('primaryBeneficiaryCoresAddressLine4', 'coresAddressLine4'),
    ('primaryBeneficiaryCoresAddressType', 'coresAddressType'),
    ('primaryBeneficiaryCoresAddressCity', 'coresAddressCity'),
    ('primaryBeneficiaryCoresAddressCountrycode', 'coresAddressCountrycode'),
    ('primaryBeneficiaryCoresAddressStatecode', 'coresAddressStatecode'),
    ('primaryBeneficiaryCoresAddressZipcode', 'coresAddressZipcode'),
    ('primaryBeneficiaryPermAddressLine1', 'permAddressLine1'),
    ('primaryBeneficiaryPermAddressLine2', 'permAddressLine2'),
    ('primaryBeneficiaryPermAddressLine3', 'permAddressLine3'),
    ('primaryBeneficiaryPermAddressLine4', 'permAddressLine4'),
    ('primaryBeneficiaryPermAddressType', 'permAddressType'),
    ('primaryBeneficiaryPermAddressCity', 'permAddressCity'),
    ('primaryBeneficiaryPermAddressCountrycode', 'permAddressCountrycode'),
    ('primaryBeneficiaryPermAddressStatecode', 'permAddressStatecode'),
    ('primaryBeneficiaryPermAddressZipcode', 'permAddressZipcode'),
    ('additionalBeneDetailsFamilyMobileFlag', 'familyMobileFlag'),
    ('additionalBeneDetailsFamilyEmailFlag', 'familyEmailFlag'),
    ('additionalBeneDetailsNominationOption', 'nominationOption'),
    ('additionalBeneDetailsOccupation', 'occupation'),
    ('additionalBeneDetailsFatherOrHusbandName', 'fatherOrHusbandName'),
    ('additionalBeneDetailsDpId', 'dpId'),
    ('additionalBeneDetailsClientId', 'clientId'),
    ('additionalBeneDetailsSharePercentEqually', 'sharePercentEqually'),
    ('additionalBeneDetailsNumOfNominees', 'numOfNominees'),
    ('bankDetailsAccountNumber', 'accountNumber'),
    ('bankDetailsBankName', 'bankName'),
    ('bankDetailsAccountType', 'accountType'),
    ('bankDetailsIfsc', 'ifsc'),
    ('bankDetailsMicr', 'micr'),
    ('bankDetailsBankAddressType', 'bankAddressType'),
    ('bankDetailsBankAddressLine1', 'bankAddressLine1'),
    ('bankDetailsBankAddressLine2', 'bankAddressLine2'),
    ('bankDetailsBankAddressLine3', 'bankAddressLine3'),
    ('bankDetailsBankAddressLine4', 'bankAddressLine4'),
    ('bankDetailsBankAddressZipcode', 'bankAddressZipcode'),
)

NSDL_REQUIRED_FIELDS = frozenset({
    'name',
    'pan',
    'panFlag',
    'grossAnnualIncome',
    'dob',
    'mobile',
    'email',
    'eStatement',
    'dematAccType',
    'dematAccSubType',
    'modeOfOperation',
    'communicationToBeSend',
    'signature',
    'coresAddressLine1',
    'coresAddressCity',
    'coresAddressCountrycode',
    'coresAddressStatecode',
    'coresAddressZipcode',
    'permAddressLine1',
    'permAddressCity',
    'permAddressCountrycode',
    'permAddressStatecode',
    'permAddressZipcode',
    'occupation',
    'dpId',
    'clientId',
    'accountNumber',
    'bankName',
    'accountType',
    'ifsc',
    'bankAddressLine1',
    'bankAddressZipcode',
})


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
        ('db_structure', '0039_rename_nsdl_pan_flag'),
    ]

    operations = [
        *(
            migrations.RenameField(
                model_name='nsdl',
                old_name=old_name,
                new_name=new_name,
            )
            for old_name, new_name in NSDL_FIELD_RENAMES
        ),
        *(
            migrations.AlterField(
                model_name='nsdl',
                name=new_name,
                field=_nsdl_field(new_name),
            )
            for _, new_name in NSDL_FIELD_RENAMES
        ),
    ]
