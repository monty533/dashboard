from types import SimpleNamespace

from django.test import SimpleTestCase

from .cdsl import _address_row, _nominee_rows, _primary_row
from .nsdl import (
    _account_type_code,
    _bank_address,
    _build_nsdl_payload,
    _build_nominees,
    _artifact_path,
    _split_address,
)
from .models import (
    NSDL_COLUMNS,
    NSDL_MANDATORY_COLUMNS,
    NSDL_OPTIONAL_COLUMNS,
    Nsdl,
)
from .nsdl_fields import nsdl_payload_metadata


class NsdlPayloadTests(SimpleTestCase):
    def test_nsdl_model_columns_have_requirement_groups(self):
        self.assertTrue(NSDL_MANDATORY_COLUMNS)
        self.assertEqual(
            NSDL_MANDATORY_COLUMNS | NSDL_OPTIONAL_COLUMNS,
            set(NSDL_COLUMNS),
        )
        self.assertTrue(NSDL_OPTIONAL_COLUMNS)
        self.assertTrue(
            NSDL_OPTIONAL_COLUMNS.isdisjoint(NSDL_MANDATORY_COLUMNS)
        )
        self.assertIn("addressLine1", NSDL_MANDATORY_COLUMNS)
        self.assertIn("nominee1Dob", NSDL_COLUMNS)
        self.assertIn("nominee3guardianAddresszipcode", NSDL_COLUMNS)
        self.assertIn("nominee1GuardianFlag", NSDL_OPTIONAL_COLUMNS)
        self.assertIn("nominee1GuardianIdentificationPan", NSDL_OPTIONAL_COLUMNS)
        self.assertIn("nominee1guardianAddressLine1", NSDL_OPTIONAL_COLUMNS)
        self.assertIn("nominee1Name", NSDL_OPTIONAL_COLUMNS)
        self.assertIn("nominee1addressLine1", NSDL_OPTIONAL_COLUMNS)
        self.assertIn("nominationOption", NSDL_OPTIONAL_COLUMNS)
        self.assertTrue(Nsdl._meta.get_field("nominee1GuardianFlag").null)
        self.assertTrue(Nsdl._meta.get_field("nominee1Name").null)
        self.assertFalse(Nsdl._meta.get_field("name").null)

    def test_nsdl_artifacts_use_text_files(self):
        self.assertEqual(_artifact_path("test-client", "request").name, "nsdl_request.txt")

    def test_bank_columns_expose_nested_payload_metadata(self):
        self.assertEqual(
            nsdl_payload_metadata("accountNumber"),
            {
                "payload_path": "instr.bankDetails.accountNumber",
                "payload_group": "bankDetails",
                "payload_group_path": "instr.bankDetails",
                "payload_key": "accountNumber",
            },
        )
        self.assertEqual(
            nsdl_payload_metadata("addressLine1"),
            {
                "payload_path": "instr.bankDetails.bankAddress.addressLine1",
                "payload_group": "bankAddress",
                "payload_group_path": "instr.bankDetails.bankAddress",
                "payload_key": "addressLine1",
            },
        )
        self.assertEqual(
            nsdl_payload_metadata("zipcode"),
            {
                "payload_path": "instr.bankDetails.bankAddress.zipcode",
                "payload_group": "bankAddress",
                "payload_group_path": "instr.bankDetails.bankAddress",
                "payload_key": "zipcode",
            },
        )
        self.assertEqual(
            nsdl_payload_metadata("panFlag"),
            {
                "payload_path": "instr.beneficiaryDetails.primaryBeneficiary.panFlag",
                "payload_group": "primaryBeneficiary",
                "payload_group_path": "instr.beneficiaryDetails.primaryBeneficiary",
                "payload_key": "panFlag",
            },
        )

    def test_primary_address_columns_expose_nested_payload_metadata(self):
        self.assertIn("coresAddressLine1", NSDL_COLUMNS)
        self.assertIn("permAddresszipcode", NSDL_COLUMNS)
        self.assertEqual(
            nsdl_payload_metadata("coresAddressLine1"),
            {
                "payload_path": (
                    "instr.beneficiaryDetails.primaryBeneficiary."
                    "beneficiaryCoresAddress.addressLine1"
                ),
                "payload_group": "beneficiaryCoresAddress",
                "payload_group_path": (
                    "instr.beneficiaryDetails.primaryBeneficiary."
                    "beneficiaryCoresAddress"
                ),
                "payload_key": "addressLine1",
            },
        )
        self.assertEqual(
            nsdl_payload_metadata("permAddresszipcode"),
            {
                "payload_path": (
                    "instr.beneficiaryDetails.primaryBeneficiary."
                    "beneficiaryPermAddress.zipcode"
                ),
                "payload_group": "beneficiaryPermAddress",
                "payload_group_path": (
                    "instr.beneficiaryDetails.primaryBeneficiary."
                    "beneficiaryPermAddress"
                ),
                "payload_key": "zipcode",
            },
        )

    def test_nominee_columns_expose_nested_payload_metadata(self):
        self.assertEqual(
            nsdl_payload_metadata("nominee1Name"),
            {
                "payload_path": (
                    "instr.beneficiaryDetails.additionalBeneDetails."
                    "listOfNominees[1].nomineeName"
                ),
                "payload_group": "listOfNominees[1]",
                "payload_group_path": (
                    "instr.beneficiaryDetails.additionalBeneDetails."
                    "listOfNominees[1]"
                ),
                "payload_key": "nomineeName",
            },
        )
        self.assertEqual(
            nsdl_payload_metadata("nominee1IdentificationPan"),
            {
                "payload_path": (
                    "instr.beneficiaryDetails.additionalBeneDetails."
                    "listOfNominees[1].nomineeIdentificationDtls.pan"
                ),
                "payload_group": "nomineeIdentificationDtls",
                "payload_group_path": (
                    "instr.beneficiaryDetails.additionalBeneDetails."
                    "listOfNominees[1].nomineeIdentificationDtls"
                ),
                "payload_key": "pan",
            },
        )
        self.assertEqual(
            nsdl_payload_metadata("nominee1guardianAddressLine1"),
            {
                "payload_path": (
                    "instr.beneficiaryDetails.additionalBeneDetails."
                    "listOfNominees[1].guardianAddress.addressLine1"
                ),
                "payload_group": "guardianAddress",
                "payload_group_path": (
                    "instr.beneficiaryDetails.additionalBeneDetails."
                    "listOfNominees[1].guardianAddress"
                ),
                "payload_key": "addressLine1",
            },
        )

    def test_nominee_payload_has_the_expected_nested_structure(self):
        nominee = _build_nominees({
            "nominee_check": "yes",
            "nominee1_name": "Nehal Divyakant Amin",
            "nominee1_pan": "ADDPA7819H",
            "nominee1_dob": "19630702",
            "nominee1_relation": "00",
            "nominee1_address1": "9 aalay bunglows shyamal",
            "nominee1_address2": "satellite Ahmedabad 380015",
            "nominee1_city": "Ahmedabad",
            "nominee1_state": "24",
            "nominee1_country": "356",
            "nominee1_pincode": "380015",
            "nominee1_mobile": "9825073242",
            "nominee1_email": "amal@technomec.co.in",
        }.get)[0]

        self.assertEqual(nominee["seqNo"], "1")
        self.assertEqual(nominee["nomineeName"], "Nehal Divyakant Amin")
        self.assertEqual(nominee["nomineeIdentificationDtls"]["pan"], "ADDPA7819H")
        self.assertIn("9 aalay bunglows shyamal", nominee["nomineeAddress"]["addressLine1"])
        self.assertEqual(nominee["nomineeAddress"]["zipcode"], "380015")
        self.assertEqual(nominee["guardianAddress"]["addressLine1"], "")


    def test_bank_values_are_read_from_client_data(self):
        bank_address = _bank_address(("ICICI Bank Ltd., Shivalli",), "380015")
        self.assertEqual(
            bank_address,
            {
                "addressType": 2,
                "addressLine1": "ICICI Bank Ltd Shivalli",
                "addressLine2": "",
                "addressLine3": "",
                "addressLine4": "",
                "zipcode": "380015",
            },
        )
        self.assertEqual(_account_type_code("10"), "10")

    def test_payload_generation_does_not_require_credentials_or_client_fields(self):
        payload, client_id = _build_nsdl_payload(
            {
                "nominee_check": "no",
                "nominee1_name": "Should not be included",
            },
            {},
        )

        self.assertEqual(client_id, "")
        self.assertEqual(payload["instr"]["beneficiaryDetails"]["primaryBeneficiary"]["name"], "")
        self.assertEqual(payload["instr"]["beneficiaryDetails"]["additionalBeneDetails"]["dpId"], "")
        primary = payload["instr"]["beneficiaryDetails"]["primaryBeneficiary"]
        additional = payload["instr"]["beneficiaryDetails"]["additionalBeneDetails"]
        self.assertEqual(primary["panFlag"], "")
        self.assertEqual(primary["eStatement"], "")
        self.assertEqual(additional["familyMobileFlag"], "")
        self.assertEqual(additional["familyEmailFlag"], "")
        self.assertNotIn("nominationOption", additional)
        self.assertNotIn("sharePercentEqually", additional)
        self.assertNotIn("numOfNominees", additional)
        self.assertNotIn("listOfNominees", additional)

    def test_nominee_payload_is_included_only_when_enabled(self):
        payload, _ = _build_nsdl_payload(
            {
                "nominee_check": "yes",
                "nominee1_name": "Nehal Divyakant Amin",
                "nominee1_pan": "ADDPA7819H",
            },
            {},
        )

        additional = payload["instr"]["beneficiaryDetails"]["additionalBeneDetails"]
        self.assertEqual(additional["nominationOption"], "Y")
        self.assertEqual(additional["numOfNominees"], 1)
        self.assertEqual(
            additional["listOfNominees"][0]["nomineeName"],
            "Nehal Divyakant Amin",
        )

    def test_payload_fields_are_read_directly_from_client_data(self):
        payload, _ = _build_nsdl_payload(
            {
                "name": "Client Name",
                "panFlag": "N",
                "eStatement": "P",
                "periodicStatement": "REG",
                "dematAccType": "04",
                "dematAccSubType": "01",
                "modeOfOperation": "1",
                "communicationToBeSend": "2",
                "familyMobileFlag": "Y",
                "familyEmailFlag": "Y",
                "bankaccountnumber": " 1234 5678 ",
                "bankname": "ICICI Bank",
                "accounttype": "saving",
                "ifsc": "icic0000001",
                "micr": "123456789",
            },
            {},
        )

        primary = payload["instr"]["beneficiaryDetails"]["primaryBeneficiary"]
        additional = payload["instr"]["beneficiaryDetails"]["additionalBeneDetails"]
        bank = payload["instr"]["bankDetails"]
        self.assertEqual(primary["panFlag"], "")
        self.assertEqual(primary["eStatement"], "")
        self.assertEqual(additional["familyMobileFlag"], "")
        self.assertEqual(additional["familyEmailFlag"], "")
        self.assertEqual(bank["accountNumber"], "12345678")
        self.assertEqual(bank["bankName"], "ICICI Bank")
        self.assertEqual(bank["accountType"], "10")
        self.assertEqual(bank["ifsc"], "ICIC0000001")
        self.assertEqual(bank["micr"], "123456789")

    def test_static_payload_values_are_read_from_nsdl_defaults(self):
        payload, _ = _build_nsdl_payload(
            {
                "panFlag": "N",
                "eStatement": "CLIENT",
                "familyMobileFlag": "CLIENT",
                "familyEmailFlag": "CLIENT",
            },
            {},
            nsdl_defaults={
                "panFlag": "Y",
                "eStatement": "E",
                "familyMobileFlag": "N",
                "familyEmailFlag": "N",
            },
        )

        primary = payload["instr"]["beneficiaryDetails"]["primaryBeneficiary"]
        additional = payload["instr"]["beneficiaryDetails"]["additionalBeneDetails"]
        self.assertEqual(primary["panFlag"], "Y")
        self.assertEqual(primary["eStatement"], "E")
        self.assertEqual(additional["familyMobileFlag"], "N")
        self.assertEqual(additional["familyEmailFlag"], "N")

    def test_long_address_is_truncated_into_payload_lines_without_rejection(self):
        lines = _split_address("x" * 300)

        self.assertEqual(len(lines), 4)
        self.assertLessEqual(len(lines[-1]), 54)


class CdslPayloadTests(SimpleTestCase):
    def test_static_template_values_are_used_for_primary_row(self):
        client = {
            "clientcode": "378811069",
            "name": "Sagar Ajay Gharat",
            "pan": "BXKPG7148B",
            "mobile": "9876543210",
            "email": "sagar@example.com",
            "aadhar_no": "5489",
            "aadhar_dob": "1998-03-24",
            "aadhar_gender": "M",
            "aadhar_fathername": "Ajay Gharat",
            "aadhar_state": "27",
            "aadhar_country": "India",
            "aadhar_pincode": "400066",
            "aadhar_dist": "Mumbai",
            "bankaccountnumber": "1234567890",
            "bankname": "AXIS BANK",
            "ifsc": "UTIB0001291",
            "nominee_check": "no",
        }
        master = SimpleNamespace(
            SndrId="TABLE-SENDER",
            BOTxnTyp="TABLE-TXN",
            SMSFclty="TABLE-SMS",
            BOUCCLkFlg="TABLE-LOCK",
        )
        credential = SimpleNamespace(DPID="33300")

        row = _primary_row(client, credential, master, "00001")

        self.assertEqual(row["SndrId"], "TABLE-SENDER")
        self.assertEqual(row["BOTxnTyp"], "TABLE-TXN")
        self.assertEqual(row["SMSFclty"], "TABLE-SMS")
        self.assertEqual(row["BOUCCLkFlg"], "TABLE-LOCK")
        self.assertEqual(row["PAN"], "BXKPG7148B")

    def test_static_template_values_are_used_for_secondary_rows(self):
        master = SimpleNamespace(
            SndrId="TABLE-SENDER",
            BOUCCLkFlg="TABLE-LOCK",
            CASMd="TABLE-CAS",
            NmStmtFlg="TABLE-NM",
        )
        credential = SimpleNamespace(DPID="33300")

        row = _address_row(
            {}, credential, master, "00001", "PERAD",
            "Flat 1, Main Road", "Ahmedabad", "24", "380015", "LOC",
        )

        self.assertEqual(row["SndrId"], "TABLE-SENDER")
        self.assertEqual(row["BOUCCLkFlg"], "TABLE-LOCK")
        self.assertEqual(row["CASMd"], "TABLE-CAS")
        self.assertEqual(row["NmStmtFlg"], "TABLE-NM")
        self.assertEqual(row["PurpCd"], "PERAD")

    def test_nominee_rows_start_from_the_editable_template(self):
        client = {
            "clientcode": "378811069",
            "nominee_check": "yes",
            "nominee1_name": "Nehal Amin",
            "nominee1_dob": "19630702",
            "nominee1_relation": "01",
            "nominee1_address1": "Main Road",
            "nominee1_city": "Ahmedabad",
            "nominee1_state": "24",
            "nominee1_pincode": "380015",
        }
        master = SimpleNamespace(SndrId="TABLE-SENDER", BOUCCLkFlg="TABLE-LOCK")
        credential = SimpleNamespace(DPID="33300")

        rows = _nominee_rows(client, credential, master, "00001")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SndrId"], "TABLE-SENDER")
        self.assertEqual(rows[0]["BOUCCLkFlg"], "TABLE-LOCK")
        self.assertEqual(rows[0]["PurpCd"], "NOMAD")
