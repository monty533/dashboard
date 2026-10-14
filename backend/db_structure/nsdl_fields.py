"""Payload paths for the fields currently declared by the NSDL model."""


PRIMARY_BENEFICIARY_FIELDS = frozenset({
    "name",
    "shortName",
    "pan",
    "panFlag",
    "grossAnnualIncome",
    "dob",
    "gender",
    "mobile",
    "email",
    "aadhar",
    "ddpiid",
    "eStatement",
    "signature",
})

ADDITIONAL_BENEFICIARY_FIELDS = frozenset({
    "familyMobileFlag",
    "familyEmailFlag",
    "nominationOption",
    "occupation",
    "fatherOrHusbandName",
    "dpId",
    "clientId",
    "sharePercentEqually",
    "numOfNominees",
})

BANK_FIELDS = frozenset({
    "accountNumber",
    "bankName",
    "accountType",
    "ifsc",
    "micr",
})

BANK_ADDRESS_FIELDS = frozenset({
    "addressType",
    "addressLine1",
    "addressLine2",
    "addressLine3",
    "addressLine4",
    "zipcode",
})

PRIMARY_ADDRESS_FIELDS = {
    f"{prefix}{suffix}": (payload_parent, payload_key)
    for prefix, payload_parent in (
        ("coresAddress", "beneficiaryCoresAddress"),
        ("permAddress", "beneficiaryPermAddress"),
    )
    for suffix, payload_key in (
        ("Line1", "addressLine1"),
        ("Line2", "addressLine2"),
        ("Line3", "addressLine3"),
        ("Line4", "addressLine4"),
        ("Type", "addressType"),
        ("city", "city"),
        ("countrycode", "countrycode"),
        ("statecode", "statecode"),
        ("zipcode", "zipcode"),
    )
}


NOMINEE_FIELD_PATHS = {}
for nominee_number in (1, 2, 3):
    nominee_path = (
        "instr",
        "beneficiaryDetails",
        "additionalBeneDetails",
        f"listOfNominees[{nominee_number}]",
    )

    for db_suffix, payload_key in (
        ("SeqNo", "seqNo"),
        ("Name", "nomineeName"),
        ("Share", "nomineeShare"),
        ("Dob", "dob"),
        ("Minor", "minor"),
        ("RelationWithNominee", "relationWithNominee"),
        ("MobileNum", "nomineeMobileNum"),
        ("EmailId", "nomineeEmailId"),
    ):
        NOMINEE_FIELD_PATHS[f"nominee{nominee_number}{db_suffix}"] = (
            *nominee_path,
            payload_key,
        )

    for db_suffix, payload_key in (
        ("Pan", "pan"),
        ("Aadhar", "aadhar"),
        ("DematAccId", "dematAccId"),
        ("SavingBankAccNo", "savingBankAccNo"),
    ):
        NOMINEE_FIELD_PATHS[
            f"nominee{nominee_number}Identification{db_suffix}"
        ] = (
            *nominee_path,
            "nomineeIdentificationDtls",
            payload_key,
        )

    for db_suffix, payload_key in (
        ("Line1", "addressLine1"),
        ("Line2", "addressLine2"),
        ("Line3", "addressLine3"),
        ("Line4", "addressLine4"),
        ("Type", "addressType"),
        ("city", "city"),
        ("countrycode", "countrycode"),
        ("statecode", "statecode"),
        ("zipcode", "zipcode"),
    ):
        NOMINEE_FIELD_PATHS[f"nominee{nominee_number}address{db_suffix}"] = (
            *nominee_path,
            "nomineeAddress",
            payload_key,
        )

    for db_suffix, payload_key in (
        ("GuardianFlag", "guardianFlag"),
        ("GuardianName", "guardianName"),
        ("GuardianRelationship", "guardianRelationship"),
        ("GuardianMobileNum", "guardianMobileNum"),
        ("GuardianEmailId", "guardianEmailId"),
    ):
        NOMINEE_FIELD_PATHS[f"nominee{nominee_number}{db_suffix}"] = (
            *nominee_path,
            payload_key,
        )

    for db_suffix, payload_key in (
        ("Pan", "pan"),
        ("Aadhar", "aadhar"),
        ("DematAccId", "dematAccId"),
        ("SavingBankAccNo", "savingBankAccNo"),
    ):
        NOMINEE_FIELD_PATHS[
            f"nominee{nominee_number}GuardianIdentification{db_suffix}"
        ] = (
            *nominee_path,
            "guardianIdentificationDtls",
            payload_key,
        )

    for db_suffix, payload_key in (
        ("Line1", "addressLine1"),
        ("Line2", "addressLine2"),
        ("Line3", "addressLine3"),
        ("Line4", "addressLine4"),
        ("Type", "addressType"),
        ("city", "city"),
        ("countrycode", "countrycode"),
        ("Statecode", "statecode"),
        ("zipcode", "zipcode"),
    ):
        NOMINEE_FIELD_PATHS[
            f"nominee{nominee_number}guardianAddress{db_suffix}"
        ] = (
            *nominee_path,
            "guardianAddress",
            payload_key,
        )


def nsdl_payload_path(column_name):
    """Return the JSON path represented by a flattened NSDL column."""
    column = str(column_name or "")

    if column in PRIMARY_BENEFICIARY_FIELDS:
        return (
            "instr",
            "beneficiaryDetails",
            "primaryBeneficiary",
            column,
        )

    if column in PRIMARY_ADDRESS_FIELDS:
        payload_parent, payload_key = PRIMARY_ADDRESS_FIELDS[column]
        return (
            "instr",
            "beneficiaryDetails",
            "primaryBeneficiary",
            payload_parent,
            payload_key,
        )

    if column in NOMINEE_FIELD_PATHS:
        return NOMINEE_FIELD_PATHS[column]

    if column in ADDITIONAL_BENEFICIARY_FIELDS:
        return (
            "instr",
            "beneficiaryDetails",
            "additionalBeneDetails",
            column,
        )

    if column in BANK_FIELDS:
        return ("instr", "bankDetails", column)

    if column in BANK_ADDRESS_FIELDS:
        return (
            "instr",
            "bankDetails",
            "bankAddress",
            column,
        )

    return (column,)


def nsdl_payload_metadata(column_name):
    """Return schema metadata used to display a nested NSDL payload."""
    path = nsdl_payload_path(column_name)
    payload_group_path = ".".join(path[:-1]).replace("[]", "") if len(path) > 1 else ""
    payload_group = path[-2].replace("[]", "") if len(path) > 1 else ""

    return {
        "payload_path": ".".join(path),
        "payload_group": payload_group,
        "payload_group_path": payload_group_path,
        "payload_key": path[-1].replace("[]", ""),
    }
