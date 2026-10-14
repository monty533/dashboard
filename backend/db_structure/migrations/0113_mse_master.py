from django.db import migrations, models


MSE_BASE_COLUMNS = (
    'ccdECM', 'ccdEDS', 'ccdCDS', 'ccdClientCode', 'ccdClientName',
    'ccdAccountType', 'ccdCategory', 'ccdPANNo', 'ccdGender',
    'ccdGuardianName', 'ccdNationality', 'ccdEmailID',
    'ccdRelationshipWithClientForEmail', 'ccdCorrespondenceClientAddress',
    'ccdCorrespondenceClientCity', 'ccdCorrespondenceClientState',
    'ccdCorrespondenceClientOtherState', 'ccdCorrespondenceClientCountry',
    'ccdCorrespondenceClientPinCode', 'ccdPermanentAddSameAsCorrs',
    'ccdPermanentAddress', 'ccdPermanentCity', 'ccdPermanentState',
    'ccdPermanentOtherState', 'ccdPermanentCountryCode',
    'ccdPermanentPincode', 'ccdMobileNo',
    'ccdRelationshipWithClientForMobile', 'ccdOfficeTelephoneNo',
    'ccdISDCode', 'ccdSTDCode', 'ccdDateofBirth', 'ccdUID', 'ccdBankName1',
    'ccdIFSCCode1', 'ccdBankAccountNo1', 'ccdBankAccountType1',
    'ccdPrimarySecondaryBank1', 'ccdCINOfClient',
    'ccdGrossAnnualIncomeRange', 'ccdGrossAnnualIncomeDate', 'ccdNetworth',
    'ccdNetworthAsOnDate', 'ccdPEPersopn', 'ccdOccupation',
    'ccdOccupationDetails', 'ccdCPCodeECM', 'ccdCPCodeEDS', 'ccdCPCodeCDS',
    'ccdRegistrationNo', 'ccdRegisteringAuthority', 'ccdRegistrationPlace',
    'ccdRegistrationDate', 'ccdInpersonVerification', 'ccdAgreementDate',
    'ccdTypeOfFacility', 'ccdUpdationFlagSMSEmail', 'ccdRelationshipCode',
    'ccdProofType', 'ccdProofNo', 'ccdPlaceOfProof', 'ccdIssueProofDate',
    'ccdStatus', 'ccdClientTypeCorporate', 'ccdPOAFunds', 'ccdPOASecurities',
    'ccdPOAFundsDate', 'ccdPOASecuritiesDate', 'ccdDDPISettlement',
    'ccdDDPISettlementDate', 'ccdDDPIPledging', 'ccdDDPIPledgingDate',
    'ccdNominationOption', 'ccdUPIOpt', 'ccdClientNameDescription', 'ccdFlag',
)
MSE_COLUMNS = (
    *(f'ccdReserved{number}' for number in range(1, 62)),
    *MSE_BASE_COLUMNS,
    *(
        f'{prefix}{number}'
        for number in range(2, 11)
        for prefix in (
            'ccdBankName', 'ccdIFSCCode', 'ccdBankAccountNo',
            'ccdBankAccountType', 'ccdPrimarySecondaryBank',
        )
    ),
    *(
        f'{prefix}{number}'
        for number in range(1, 6)
        for prefix in (
            'ccdDepositoryName', 'ccdDepositoryId',
            'ccdBeneficiaryAccountNo', 'ccdPrimarySecondaryDP',
        )
    ),
    *(
        f'ccd{provider}{suffix}'
        for provider in ('ECM', 'EDS', 'CDS')
        for suffix in (
            'CPName', 'CPPANNo', 'CPEmailId', 'CorrespondenceCPAddress',
            'CorrespondenceCPCity', 'CorrespondenceCPState',
            'CorrespondenceCPOtherState', 'CorrespondenceCPCountry',
            'CorrespondenceCPPinCode', 'CPMobileNo', 'CPISDCode', 'CPSTDCode',
            'CPTelephoneNo',
        )
    ),
    *(
        f'ccdCP{suffix}{number}'
        for number in range(1, 7)
        for suffix in (
            'Name', 'Designation', 'PANNo', 'Address', 'ContactDetails', 'DIN',
            'EmailID',
        )
    ),
)


def _create_mse_table(apps, schema_editor):
    """Create MSE with a dynamic row format on MySQL.

    MySQL's default COMPACT row format can reject a wide table even when its
    columns are TEXT. DYNAMIC stores the TEXT values off-row and keeps this
    provider schema compatible with the Master screen.
    """
    connection = schema_editor.connection
    table_name = schema_editor.quote_name('mse')
    if 'mse' in connection.introspection.table_names():
        return

    if connection.vendor == 'mysql':
        columns = [
            '`id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY',
            *[f'`{column}` VARCHAR(20) CHARACTER SET ascii NULL' for column in MSE_COLUMNS],
        ]
        schema_editor.execute(
            f'CREATE TABLE {table_name} ({", ".join(columns)}) '
            'ENGINE=InnoDB ROW_FORMAT=DYNAMIC'
        )
        return

    # Development fallback for non-MySQL databases.
    schema_editor.execute(
        f'CREATE TABLE {table_name} ('
        '"id" BIGINT PRIMARY KEY, '
        + ', '.join(f'"{column}" TEXT NULL' for column in MSE_COLUMNS)
        + ')'
    )


def _drop_mse_table(apps, schema_editor):
    schema_editor.execute(schema_editor.sql_delete_table % schema_editor.quote_name('mse'))


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0112_alter_krastatusmaster_app_status_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_create_mse_table, _drop_mse_table),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='Mse',
                    fields=[
                        (
                            'id',
                            models.BigAutoField(
                                db_column='id',
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        *[
                            (
                                column,
                                models.CharField(
                                    blank=True,
                                    db_column=column,
                                    max_length=20,
                                    null=True,
                                ),
                            )
                            for column in MSE_COLUMNS
                        ],
                    ],
                    options={
                        'db_table': 'mse',
                    },
                ),
            ],
        ),
    ]
