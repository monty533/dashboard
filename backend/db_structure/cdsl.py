"""CDSL UDiFF payload generation and resumable provider workflow.

The older CDSL integration was implemented as a Flask blueprint.  This module
keeps the same UDiFF row layout while using the Django models and API patterns
used by the NSE, BSE, and NSDL integrations.
"""

import base64
import binascii
import csv
import datetime as dt
import hashlib
import io
import json
import logging
import re
import zipfile
from collections.abc import Mapping
from urllib.parse import quote

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from django.conf import settings
from django.db import DatabaseError, models, transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Cdsl,
    CdslCredentials,
    CdslIncomeRangeMaster,
    CdslStateCodeMaster,
    CdslUpload,
    UserDetails,
)
from .push_tracking import (
    reject_if_api_not_selected,
    reject_if_provider_order_blocked,
)
from .views import _requested_company_user


logger = logging.getLogger(__name__)

CDSL_CLIENT_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}\Z")
CDSL_FILE_KINDS = {
    "request": ("request.txt", "text/plain"),
    "response": ("response.txt", "text/plain"),
    "log": ("log.txt", "text/plain"),
    "archive": ("request.zip", "application/zip"),
    "response_archive": ("response.zip", "application/zip"),
}

# These are the live CDSL endpoints used by the legacy integration.  Keeping
# them together makes the three-stage workflow easy to audit and allows a
# deployment to override them from Django settings when CDSL provides a UAT
# gateway.
CDSL_API_URLS = {
    "auth": "https://web.cdslindia.com/AuthWeb/api/CDASAuthorization/APIAuth",
    "upload": "https://apigt.cdsl.co.in/Commonweb/api/BOAPI/HrmSetUpload",
    "status": "https://web.cdslindia.com/Commonweb/api/CDASAPI/Status",
    "download": "https://web.cdslindia.com/Commonweb/api/CDASAPI/Download",
    "referer": "https://web.cdslindia.com/CommonWeb/api/CDASAPI/ResponseAPI",
}
CDSL_STATUS_CLOSED = {
    "closed", "close", "completed", "complete", "accepted",
    "success", "successful", "successfully",
}
CDSL_STATUS_FAILED = {"rejected", "failed", "failure", "error"}
CDSL_STAGE_UPLOAD = "upload"
CDSL_STAGE_STATUS = "status"
CDSL_STAGE_DOWNLOAD = "download"


def _cdsl_credential_fields():
    """Return editable scalar credential fields declared by the model."""
    return tuple(
        field.name
        for field in CdslCredentials._meta.concrete_fields
        if field.editable and not field.primary_key and not field.is_relation
    )


CDSL_FIELDS = tuple(
    field.name
    for field in Cdsl._meta.concrete_fields
    if not field.primary_key
)

CDSL_PRIMARY_DYNAMIC_FIELDS = frozenset({
    "ClntId",
    "BnfcrySubTp",
    "FrstNm",
    "MddlNm",
    "LastNm",
    "BnfcryShrtNm",
    "ScndHldrNmOfFthr",
    "BirthDt",
    "Gndr",
    "PAN",
    "PANVrfyFlg",
    "UID",
    "AdhrAuthntcnWthUID",
    "PrmryISDCd",
    "MobNb",
    "EmailAdr",
    "NoNmntnFlg",
    "GrssAnlIncmRg",
    "INIFSC",
    "MICRCd",
    "Mndt",
    "EdctnLvl",
    "BkAcctTp",
    "BnfcryBkAcctNb",
    "BnfcryBkNm",
    "Ocptn",
    "SndrRefNb1",
    "UnqClntId",
    "Ctry",
    "PstCd",
    "CtrySubDvsnCd",
    "CitySeqNb",
    "NmnorGrdnAddPrsnt",
    "MnrNmnGrdnAddPrsnt",
    "Adr1",
    "Adr2",
    "Adr3",
    "Adr4",
    "SetUpDt",
})

# These values are generated for each file/row and must not be copied from the
# editable CDSL template row.
CDSL_SYSTEM_FIELDS = {
    "CntrlSctiesDpstryPtcpt",
    "BtchId",
    "SndrDt",
    "RcvDt",
    "RcrdNb",
    "RcdSRNumber",
}

CDSL_DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%d%m%Y",
    "%m/%d/%Y",
)


class CdslError(ValueError):
    """A safe, user-facing CDSL configuration or payload error."""


def _text(value):
    return "" if value is None else str(value).strip()


def _yes(value):
    return _text(value).casefold() in {"1", "true", "yes", "y"}


def _getter(record):
    if isinstance(record, Mapping):
        values = {str(key).casefold(): value for key, value in record.items()}
    else:
        values = {
            field.name.casefold(): getattr(record, field.name, "")
            for field in record._meta.concrete_fields
        }

    def get(*names, default=""):
        for name in names:
            value = values.get(str(name).casefold(), "")
            if value is not None and _text(value):
                return _text(value)
        return default

    return get


def _parse_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value

    value = _text(value)
    if not value:
        return None

    match = re.search(r"\d{1,4}[-/]\d{1,4}[-/]\d{1,4}|\d{8}", value)
    candidate = match.group(0) if match else value.split(" ", 1)[0]
    for date_format in CDSL_DATE_FORMATS:
        try:
            return dt.datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    return None


def make_dob_for_cdsl(value):
    """Return the legacy helper's result without rejecting payload generation."""
    parsed = _parse_date(value)
    return {
        "dob": parsed.strftime("%d-%m-%Y") if parsed else "",
        "status": bool(parsed),
    }


def _cdsl_date(value):
    parsed = _parse_date(value)
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def _clean_address(value):
    value = _text(value)
    value = re.sub(r"[^A-Za-z0-9 /]+", " ", value)
    return " ".join(value.replace(",", " ").split())


def address_breaker_cdsl(address, length=55):
    """Split an address into the three UDiFF address columns."""
    words = _clean_address(address).split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > length:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return tuple((lines + ["", "", ""])[:3])


def _safe_clientcode(clientcode):
    clientcode = _text(clientcode)
    return clientcode if CDSL_CLIENT_CODE_PATTERN.fullmatch(clientcode) else ""


def _model_defaults(cdsl_master):
    if cdsl_master is None:
        return {
            field.name: _text(field.default)
            if field.default is not models.NOT_PROVIDED else ""
            for field in Cdsl._meta.concrete_fields
            if not field.primary_key
        }
    return {
        field: _text(getattr(cdsl_master, field, ""))
        for field in CDSL_FIELDS
    }


def _normalise_master(cdsl_master):
    """Provide empty values for partial master objects used by callers/tests."""
    if cdsl_master is None:
        cdsl_master = type("EmptyCdslMaster", (), {})()
    for field in CDSL_FIELDS:
        if not hasattr(cdsl_master, field):
            setattr(cdsl_master, field, "")
    return cdsl_master


def _put(row, **values):
    """Update only columns that exist on the CDSL model."""
    row.update({key: _text(value) for key, value in values.items() if key in row})


def _restore_configured_defaults(row, cdsl_master, dynamic_fields):
    """Keep values configured in the CDSL table for non-client fields."""
    if cdsl_master is None:
        return
    for field in CDSL_FIELDS:
        configured = _text(getattr(cdsl_master, field, ""))
        if (
            configured
            and field not in dynamic_fields
            and field not in CDSL_SYSTEM_FIELDS
        ):
            row[field] = configured


def _template_row(cdsl_master, credential, batch_number, dynamic_fields=()):
    """Start every CDSL record from the editable model template.

    Values that belong to a client are cleared before the row-specific values
    are applied. This prevents a value saved in the CDSL master row from
    leaking into another client's payload while keeping every static template
    value editable from the schema screen.
    """
    # Every column comes from the actual Cdsl model/template row first. This
    # keeps values edited in the frontend available to every generated row.
    row = _model_defaults(cdsl_master)
    for field in dynamic_fields:
        if field in row:
            row[field] = ""
    _put(row, **_system_values(credential, cdsl_master, batch_number))
    return row


def _name_parts(name):
    parts = _text(name).upper().split()
    if not parts:
        return "", "", "."
    if len(parts) == 1:
        return parts[0], "", "."
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def _normalise_master_label(value):
    return re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()


def _master_code(model, label_field, code_field, value):
    value = _text(value)
    if not value:
        return ""
    try:
        direct = model.objects.filter(
            **{f"{label_field}__iexact": value}
        ).values_list(code_field, flat=True).first()
        if _text(direct):
            return _text(direct)

        wanted = _normalise_master_label(value)
        for label, code in model.objects.values_list(label_field, code_field):
            if _normalise_master_label(label) == wanted and _text(code):
                return _text(code)

        # Forms may already submit the CDSL code instead of its label.
        code = model.objects.filter(
            **{f"{code_field}__iexact": value}
        ).values_list(code_field, flat=True).first()
        return _text(code)
    except DatabaseError:
        logger.exception("Unable to read CDSL master table %s", model._meta.db_table)
        return ""


def _state_code(value):
    value = _text(value)
    if not value:
        return ""
    if re.fullmatch(r"\d{1,2}", value):
        return value.zfill(2)
    return _master_code(
        CdslStateCodeMaster,
        "state_name",
        "state_code",
        value,
    ) or value


def _income_code(value):
    value = _text(value)
    if not value:
        return ""
    return _master_code(
        CdslIncomeRangeMaster,
        "income_range",
        "income_code",
        value,
    ) or value


def _mobile(value):
    return re.sub(r"\D", "", _text(value))


def _system_values(credential, cdsl_master, batch_number):
    now = timezone.localtime()
    return {
        "CntrlSctiesDpstryPtcpt": _text(credential.DPID),
        "BtchId": batch_number,
        "SndrId": _text(getattr(cdsl_master, "SndrId", "")) or "APIMOD",
        "SndrDt": now.strftime("%Y-%m-%d"),
        "RcvDt": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "RcrdNb": "1",
    }


def _primary_row(client, credential, cdsl_master, batch_number):
    cdsl_master = _normalise_master(cdsl_master)
    get = _getter(client)
    row = _template_row(
        cdsl_master,
        credential,
        batch_number,
        CDSL_PRIMARY_DYNAMIC_FIELDS,
    )

    clientcode = _text(get("clientcode"))
    name = get("aadhaar_name").upper()
    first_name, middle_name, last_name = _name_parts(name)
    father_name = get("aadhaar_fathername").upper()
    father_name = re.sub(r"\bS/O\s*:?[ ]*", "", father_name).strip()
    aadhar = get("aadhaar_no")
    aadhar_value = "" if aadhar.casefold() in {"na", "xxxxxxxxxxxx"} else aadhar.replace("x", "X").replace("*", "X")
    mobile = _mobile(get("mobile"))
    nominee_enabled = _yes(get("nominee_check"))
    pledge_standing_instruction_enabled = _yes(get("pledge_standing_instruction"))
    bsda = get("bsda_flag")
    bsda_value = _text(getattr(cdsl_master, "BSDAFlg")) if bsda.casefold() == "yes" else "NBSD"
    if _text(row.get("BSDAFlg")):
        bsda_value = row["BSDAFlg"]

    _put(
        row,
        ClntId=get("dpid"),
        BnfcrySubTp=_text(getattr(cdsl_master, "BnfcrySubTp")) if nominee_enabled else "IRNNO",
        Purpse= _text(getattr(cdsl_master, "Purpse")),
        FrstNm=first_name,
        MddlNm=middle_name,
        LastNm=last_name,
        BnfcryShrtNm=last_name or first_name,
        ScndHldrNmOfFthr=father_name,
        BirthDt=_cdsl_date(get("aadhaar_dob")),
        Gndr=get("aadhaar_gender").upper(),
        PAN=get("pan").upper(),
        PANVrfyFlg=_text(getattr(cdsl_master, "PANVrfyFlg")) if get("pan") else "",
        UID=aadhar_value,
        AdhrAuthntcnWthUID= _text(getattr(cdsl_master, "AdhrAuthntcnWthUID")) if aadhar_value else "",
        SMSFclty=_text(getattr(cdsl_master, "SMSFclty")),
        PrmryISDCd=  _text(getattr(cdsl_master, "PrmryISDCd")) if mobile else "",
        MobNb=mobile,
        EmailAdr=get("email").lower(),
        NoNmntnFlg=_text(getattr(cdsl_master, "NoNmntnFlg")) if nominee_enabled else "NO",
        StgInstr= _text(getattr(cdsl_master, "StgInstr")),
        GrssAnlIncmRg=_income_code(get("annual_income")),
        INIFSC=get("ifsc").upper(),
        MICRCd=get("micr").upper(),
        DvddCcy=_text(getattr(cdsl_master, "DvddCcy")),
        DvddBkCcy=_text(getattr(cdsl_master, "DvddBkCcy")),
        Mndt=get("ECS_MANDATE"),
        EdctnLvl=get("education"),
        AnlRptFlg=_text(getattr(cdsl_master, "AnlRptFlg")),
        BnfclOwnrSttlmCyclCd=_text(getattr(cdsl_master, "BnfclOwnrSttlmCyclCd")),
        Ntlty= _text(getattr(cdsl_master, "Ntlty")),
        AncstrlFlg= _text(getattr(cdsl_master, "AncstrlFlg")),
        PldgStgInstrFlg= _text(getattr(cdsl_master, "PldgStgInstrFlg")) if pledge_standing_instruction_enabled else "NO",
        BkAcctTp=get("accounttype"),
        BnfcryAcctCtgy=_text(getattr(cdsl_master, "BnfcryAcctCtgy")),
        BnfcryBkAcctNb=get("bankaccountnumber"),
        BnfcryBkNm=get("bankname"),
        BnfcryTaxDdctnSts=_text(getattr(cdsl_master, "BnfcryTaxDdctnSts")),
        ClrSysId=_text(getattr(cdsl_master, "ClrSysId")),
        BSDAFlg=bsda_value,
        Ocptn=get("occupation"),
        PMSClntAcctFlg= _text(getattr(cdsl_master, "PMSClntAcctFlg")),
        FrstClntOptnToRcvElctrncStmtFlg= _text(getattr(cdsl_master, "FrstClntOptnToRcvElctrncStmtFlg")),
        ComToBeSentTo= _text(getattr(cdsl_master, "ComToBeSentTo")),
        AccntOpSrc= _text(getattr(cdsl_master, "AccntOpSrc")),
        SndrRefNb1=clientcode,
        CtdnFlg= _text(getattr(cdsl_master, "CtdnFlg")),
        NmneeMnrInd=_text(getattr(cdsl_master, "NmneeMnrInd")),
        POAToOprtAcct= _text(getattr(cdsl_master, "POAToOprtAcct")),
        UnqClntId=clientcode,
        PurpCd= _text(getattr(cdsl_master, "PurpCd")),
        AdrPrefFlg= _text(getattr(cdsl_master, "AdrPrefFlg")),
        Ctry= _text(getattr(cdsl_master, "Ctry")) if get("aadhaar_country") else "",
        PstCd=get("aadhaar_pincode", "aadhar_pincode", "adhar_pincode"),
        CtrySubDvsnCd=_state_code(get("aadhaar_state", "aadhar_state", "adhar_state", "state")),
        CitySeqNb= _text(getattr(cdsl_master, "CitySeqNb")) if get("aadhaar_dist") else "",
        LclAddPrsnt= _text(getattr(cdsl_master, "LclAddPrsnt")),
        BnkAddPrsnt= _text(getattr(cdsl_master, "BnkAddPrsnt")),
        NmnorGrdnAddPrsnt=_text(getattr(cdsl_master, "NmnorGrdnAddPrsnt")) if nominee_enabled else "NO",
        MnrNmnGrdnAddPrsnt=_text(getattr(cdsl_master, "MnrNmnGrdnAddPrsnt")),
        FrgnOrCorrAddPrsnt=_text(getattr(cdsl_master, "FrgnOrCorrAddPrsnt")),
        BnfclOwnrAcctOfPMSFlg=_text(getattr(cdsl_master, "BnfclOwnrAcctOfPMSFlg")),
        CnsntMode=_text(getattr(cdsl_master, "CnsntMode")) if bsda_value == "NBSD" else "",
        SetUpDt=timezone.localdate().strftime("%Y-%m-%d"),
    )

    address = " ".join(
        filter(
            None,
            (
                get("aadhaar_house"),
                get("aadhaar_address"),
                get("addressline1"),
                get("addressline2"),
                get("addressline3"),
            ),
        )
    )
    address1, address2, address3 = address_breaker_cdsl(address)
    _put(
        row,
        Adr1=address1,
        Adr2=address2,
        Adr3=address3,
        Adr4=get("aadhaar_dist").replace("-", " "),
    )
    _restore_configured_defaults(row, cdsl_master, CDSL_PRIMARY_DYNAMIC_FIELDS)
    return row


def _address_row(*args):
    # Accept the older helper signature with an unused leading client value;
    # existing payload generation uses the shorter nine-argument form.
    if len(args) == 10:
        _, credential, cdsl_master, batch_number, purpose_code, address, city, state, pincode, preference = args
    elif len(args) == 9:
        credential, cdsl_master, batch_number, purpose_code, address, city, state, pincode, preference = args
    else:
        raise TypeError("_address_row expects 9 or 10 positional arguments")
    cdsl_master = _normalise_master(cdsl_master)
    row = _template_row(
        cdsl_master,
        credential,
        batch_number,
        CDSL_PRIMARY_DYNAMIC_FIELDS,
    )
    line1, line2, line3 = address_breaker_cdsl(address)
    _put(
        row,
        Purpse= _text(getattr(cdsl_master, "Purpse")),
        CASMd=getattr(cdsl_master, "CASMd", ""),
        PurpCd=purpose_code,
        AdrPrefFlg=preference,
        Adr1=line1,
        Adr2=line2,
        Adr3=line3,
        Adr4=_text(city).replace("-", " "),
        Ctry=_text(getattr(cdsl_master, "Ctry")) if _text(city) else "",
        PstCd=pincode,
        CtrySubDvsnCd=_state_code(state),
        CitySeqNb=_text(getattr(cdsl_master, "CitySeqNb")) if _text(city) else "",
        NmStmtFlg=getattr(cdsl_master, "NmStmtFlg", ""),
    )
    return row


def _nominee_rows(client, credential, cdsl_master, batch_number):
    cdsl_master = _normalise_master(cdsl_master)
    get = _getter(client)
    if not _yes(get("nominee_check")):
        logger.debug("CDSL nominee rows skipped: clientcode=%s", get("clientcode"))
        return []

    rows = []
    for sequence in (1, 2, 3):
        name = get(f"nominee{sequence}_name")
        if not name:
            continue
        nominee_get = lambda *field_names: get(
            *(f"nominee{sequence}_{field}" for field in field_names)
        )
        first_name, middle_name, last_name = _name_parts(name)
        mobile = _mobile(nominee_get("mobile"))
        relation = nominee_get("relation").upper()
        row = _template_row(
            cdsl_master,
            credential,
            batch_number,
            CDSL_PRIMARY_DYNAMIC_FIELDS,
        )
        nominee_address = " ".join(
            filter(None, (nominee_get("address1"), nominee_get("address2")))
        )
        address1, address2, address3 = address_breaker_cdsl(nominee_address)
        guardian_name = get(f"guardian_name_{sequence}")
        _put(
            row,
            Purpse="NM",
            FrstNm=first_name,
            MddlNm=middle_name,
            LastNm=last_name or ".",
            BnfcryShrtNm=last_name or first_name,
            BirthDt=_cdsl_date(nominee_get("dob")),
            PAN=nominee_get("pan").upper(),
            PrmryISDCd=  _text(getattr(cdsl_master, "PrmryISDCd")) if mobile else "",
            MobNb=mobile,
            EmailAdr=nominee_get("email").lower(),
            NmneeMnrInd=_text(getattr(cdsl_master, "NmneeMnrInd")) if guardian_name else "NO",
            SrlNbr=str(sequence),
            NmneePctgOfShr=nominee_get("percentage"),
            RsdlSecFlg="YES" if sequence == 1 else "NO",
            RltshWthBnfclOwnr=relation,
            Rmk="Others" if relation == "OTH" else "",
            PurpCd=("NOMAD", "SENAD", "THNAD")[sequence - 1],
            Adr1=address1,
            Adr2=address2,
            Adr3=address3,
            Adr4=nominee_get("city").replace("-", " "),
            Ctry=_text(getattr(cdsl_master, "Ctry")) if nominee_get("city") else "",
            PstCd=nominee_get("pincode"),
            CtrySubDvsnCd=_state_code(nominee_get("state")),
            CitySeqNb=_text(getattr(cdsl_master, "CitySeqNb")) if nominee_get("city") else "",
            NmStmtFlg=getattr(cdsl_master, "NmStmtFlg", ""),
        )
        rows.append(row)
    logger.info(
        "CDSL nominee rows built: clientcode=%s count=%s",
        get("clientcode"),
        len(rows),
    )
    return rows


def _build_cdsl_rows(client, credential, cdsl_master, batch_number):
    get = _getter(client)
    rows = [_primary_row(client, credential, cdsl_master, batch_number)]
    rows.append(
        _address_row(
            credential,
            cdsl_master,
            batch_number,
            "PERAD",
            " ".join(
                filter(
                    None,
                    (
                        get("aadhaar_address"),
                        get("addressline1"),
                        get("addressline2"),
                        get("addressline3"),
                    ),
                )
            ),
            get("aadhaar_dist"),
            get("aadhaar_state"),
            get("aadhaar_pincode"),
            "LOC",
        )
    )
    rows.append(
        _address_row(
            credential,
            cdsl_master,
            batch_number,
            "BBADD",
            get("bankaddress"),
            get("bank_city"),
            get("bank_state"),
            get("bank_pincode"),
            "COR",
        )
    )
    rows.extend(_nominee_rows(client, credential, cdsl_master, batch_number))

    for sequence, row in enumerate(rows, start=1):
        row["RcdSRNumber"] = str(sequence)
    logger.info(
        "CDSL UDiFF rows built: clientcode=%s rows=%s nominees=%s",
        get("clientcode"),
        len(rows),
        max(0, len(rows) - 3),
    )
    return rows


def _csv_text(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CDSL_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _save_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _save_binary(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(path)


def _save_cdsl_artifacts(clientcode, csv_body, response_body, log_body, csv_filename):
    directory = settings.BASE_DIR / "static" / "cdsl_data" / _safe_clientcode(clientcode)
    directory.mkdir(parents=True, exist_ok=True)
    _save_text(directory / "request.txt", csv_body)
    _save_text(directory / "response.txt", response_body)
    _save_text(directory / "log.txt", log_body)
    archive_path = directory / "request.zip"
    temporary_archive = directory / ".request.zip.tmp"
    with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(csv_filename, csv_body)
    temporary_archive.replace(archive_path)
    logger.info(
        "CDSL artifacts saved: clientcode=%s request_bytes=%s archive=%s",
        clientcode,
        len(csv_body.encode("utf-8")),
        archive_path.name,
    )
    return directory


def _save_cdsl_error_artifact(clientcode, message, provider_response=None, stage=""):
    """Save a structured CDSL error/provider response for the dashboard."""
    error_message = _text(message)
    error_data = {
        "success": False,
        "error": error_message,
        "message": error_message,
        "msg": error_message,
    }
    if stage:
        error_data["stage"] = stage
    if provider_response is not None:
        error_data["provider_response"] = provider_response
    error_body = json.dumps(error_data, ensure_ascii=False, indent=2, default=str)
    directory = settings.BASE_DIR / "static" / "cdsl_data" / _safe_clientcode(clientcode)
    directory.mkdir(parents=True, exist_ok=True)
    _save_text(directory / "response.txt", error_body)
    _save_text(directory / "log.txt", error_body)
    logger.info(
        "CDSL response artifact saved: clientcode=%s stage=%s error=%s",
        clientcode,
        stage or "local",
        bool(error_message),
    )


def _cdsl_urls():
    """Return configured CDSL endpoints while retaining legacy defaults."""
    configured = getattr(settings, "CDSL_API_URLS", {}) or {}
    return {
        key: _text(configured.get(key)) or default
        for key, default in CDSL_API_URLS.items()
    }


def _cdsl_key(value):
    key = _text(value).encode("utf-8")
    if len(key) not in {16, 24, 32}:
        raise CdslError("CDSL AES key must contain 16, 24, or 32 characters.")
    return key


def _cdsl_encrypt(value, aes_key):
    """Encrypt a CDSL value using its legacy AES-CBC/zero-IV format."""
    cipher = AES.new(_cdsl_key(aes_key), AES.MODE_CBC, iv=b"\0" * AES.block_size)
    return base64.b64encode(cipher.encrypt(pad(_text(value).encode("utf-8"), AES.block_size))).decode("ascii")


def _cdsl_auth_sign(payload, aes_key):
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()
    return _cdsl_encrypt(digest, aes_key)


def _safe_headers(headers):
    return {
        key: "[REDACTED]" if key.casefold() in {"authtoken", "authsign"} else value
        for key, value in headers.items()
    }


def _cdsl_success(value):
    return value is True or _text(value).casefold() in {"1", "true", "yes", "y", "success"}


def _cdsl_json_response(response, stage):
    """Decode a CDSL JSON response and turn malformed replies into errors."""
    try:
        data = response.json()
    except ValueError as exc:
        raise CdslError(
            f"CDSL {stage} API returned an invalid response: {response.text[:500]}"
        ) from exc
    if not isinstance(data, Mapping):
        raise CdslError(f"CDSL {stage} API returned an invalid response.")
    return dict(data)


def _cdsl_authenticate(credential, urls):
    """Authenticate and return the CDSL token used by the next API."""
    encrypted_password = _cdsl_encrypt(credential.Password, credential.AES_key)
    payload = {
        "DPID": _text(credential.DPID),
        "UserID": _text(credential.UserID),
        "Password": encrypted_password,
    }
    payload_text = json.dumps(payload, separators=(",", ":"))
    headers = {
        "Referer": urls["referer"],
        "AuthSign": _cdsl_auth_sign(payload_text, credential.AES_key),
        "Content-Type": "application/json",
    }
    logger.info("CDSL authentication started: dpid=%s", _text(credential.DPID))
    response = requests.post(
        urls["auth"],
        headers=headers,
        data=payload_text,
        timeout=getattr(settings, "CDSL_API_TIMEOUT", 90),
    )
    data = _cdsl_json_response(response, "authentication")
    if not response.ok or not _cdsl_success(data.get("success")):
        error = _text(
            _nested_value(data, "AuthResponse", "ErrorMessage")
            or data.get("message")
            or data.get("error")
            or response.text
        )
        raise CdslProviderError(error or "CDSL authentication failed.", data, "auth")
    token = _text(data.get("AuthToken") or data.get("authToken"))
    if not token:
        raise CdslProviderError("CDSL authentication token was not returned.", data, "auth")
    logger.info("CDSL authentication succeeded: dpid=%s", _text(credential.DPID))
    return token, {
        "api": "auth",
        "url": urls["auth"],
        "headers": _safe_headers(headers),
        "payload": {**payload, "Password": "[REDACTED]"},
        "response": data,
    }


def _nested_value(value, *keys):
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return ""
        current = current.get(key)
    return current


class CdslProviderError(CdslError):
    """A CDSL API error with the provider response preserved."""

    def __init__(self, message, provider_response=None, stage=""):
        super().__init__(message)
        self.provider_response = provider_response
        self.stage = stage


def _cdsl_upload_archive(credential, token, archive_path, urls):
    payload = {"UploadId": "08", "Signature": ""}
    payload_text = json.dumps(payload, separators=(",", ":"))
    archive_bytes = archive_path.read_bytes()
    headers = {
        "AuthToken": token,
        "AuthSign": _cdsl_auth_sign(payload_text, credential.AES_key),
        "FileComputeHash": hashlib.sha256(archive_bytes).hexdigest().upper(),
    }
    logger.info(
        "CDSL archive upload started: filename=%s bytes=%s",
        archive_path.name,
        len(archive_bytes),
    )
    with archive_path.open("rb") as archive_file:
        response = requests.post(
            urls["upload"],
            headers=headers,
            data=payload,
            files={"archive": (archive_path.name, archive_file, "application/zip")},
            timeout=getattr(settings, "CDSL_API_TIMEOUT", 90),
        )
    data = _cdsl_json_response(response, "upload")
    if not response.ok or not _cdsl_success(data.get("success")):
        error = _text(
            _nested_value(data, "UploadResponse", "ErrorMessage")
            or data.get("message")
            or data.get("error")
            or response.text
        )
        raise CdslProviderError(error or "CDSL archive upload failed.", data, CDSL_STAGE_UPLOAD)
    acknowledgment_id = _text(data.get("AcknowledgmentID") or data.get("AcknowledgementID"))
    if not acknowledgment_id:
        raise CdslProviderError("CDSL upload did not return an acknowledgment ID.", data, CDSL_STAGE_UPLOAD)
    logger.info("CDSL archive upload succeeded: acknowledgment_id=%s", acknowledgment_id)
    return acknowledgment_id, {
        "api": "upload",
        "url": urls["upload"],
        "headers": _safe_headers(headers),
        "payload": payload,
        "response": data,
    }


def _cdsl_status(credential, token, acknowledgment_id, urls):
    payload = {"AcknowledgmentID": acknowledgment_id, "Signature": ""}
    payload_text = json.dumps(payload, separators=(",", ":"))
    headers = {
        "AuthToken": token,
        "AuthSign": _cdsl_auth_sign(payload_text, credential.AES_key),
        "Content-Type": "application/json",
    }
    logger.info("CDSL status check started: acknowledgment_id=%s", acknowledgment_id)
    response = requests.post(
        urls["status"],
        headers=headers,
        data=payload_text,
        timeout=getattr(settings, "CDSL_API_TIMEOUT", 90),
    )
    data = _cdsl_json_response(response, "status")
    if not response.ok:
        error = _text(
            _nested_value(data, "UploadStatusResponse", "ErrorMessage")
            or data.get("message")
            or data.get("error")
            or response.text
        )
        raise CdslProviderError(error or "CDSL status API failed.", data, CDSL_STAGE_STATUS)
    status_text = _text(data.get("Status") or _nested_value(data, "UploadStatusResponse", "Status"))
    if not _cdsl_success(data.get("success")):
        error = _text(
            _nested_value(data, "UploadStatusResponse", "ErrorMessage")
            or data.get("message")
            or data.get("error")
            or "CDSL status API rejected the acknowledgment ID."
        )
        raise CdslProviderError(error, data, CDSL_STAGE_STATUS)
    if not status_text:
        raise CdslProviderError("CDSL status API did not return a status.", data, CDSL_STAGE_STATUS)
    if _cdsl_status_is_failed(status_text):
        raise CdslProviderError(f"CDSL status: {status_text}", data, CDSL_STAGE_STATUS)
    logger.info(
        "CDSL status received: acknowledgment_id=%s status=%s closed=%s",
        acknowledgment_id,
        status_text,
        _cdsl_status_is_closed(status_text),
    )
    return status_text, {
        "api": "status",
        "url": urls["status"],
        "headers": _safe_headers(headers),
        "payload": payload,
        "response": data,
    }


def _cdsl_status_is_closed(status_text):
    normalized = re.sub(r"[^a-z]+", " ", _text(status_text).casefold()).strip()
    return any(
        normalized == value or normalized.endswith(f" {value}") or f" {value} " in f" {normalized} "
        for value in CDSL_STATUS_CLOSED
    )


def _cdsl_status_is_failed(status_text):
    normalized = re.sub(r"[^a-z]+", " ", _text(status_text).casefold()).strip()
    return any(
        normalized == value or normalized.endswith(f" {value}") or f" {value} " in f" {normalized} "
        for value in CDSL_STATUS_FAILED
    )


def _cdsl_download_response(credential, token, filename, urls):
    payload = {"UploadID": "08", "UploadFileName": filename, "Signature": ""}
    payload_text = json.dumps(payload, separators=(",", ":"))
    headers = {
        "Referer": urls["referer"],
        "AuthToken": token,
        "AuthSign": _cdsl_auth_sign(payload_text, credential.AES_key),
        "Content-Type": "application/json",
    }
    logger.info("CDSL response download started: filename=%s", filename)
    response = requests.post(
        urls["download"],
        headers=headers,
        data=payload_text,
        timeout=getattr(settings, "CDSL_API_TIMEOUT", 90),
    )
    data = _cdsl_json_response(response, "download")
    if not response.ok or not _cdsl_success(data.get("success")):
        error = _text(
            _nested_value(data, "DownloadResponseFile", "ErrorMessage")
            or data.get("message")
            or data.get("error")
            or response.text
        )
        raise CdslProviderError(error or "CDSL response download failed.", data, CDSL_STAGE_DOWNLOAD)
    logger.info("CDSL response download succeeded: filename=%s", filename)
    return data, {
        "api": "download",
        "url": urls["download"],
        "headers": _safe_headers(headers),
        "payload": payload,
        "response": data,
    }


def _cdsl_response_archive(data):
    encoded = _text(data.get("ResponseFilebuffer") or data.get("ResponseFileBuffer"))
    if not encoded:
        return b""
    try:
        return base64.b64decode(encoded)
    except (ValueError, binascii.Error) as exc:
        raise CdslError("CDSL returned an invalid response file.") from exc


def _cdsl_validate_response_archive(archive_bytes):
    """Return a provider rejection message when the downloaded file rejects."""
    if not archive_bytes:
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            text_names = [name for name in names if not name.endswith("/")]
            for name in text_names:
                content = archive.read(name).decode("utf-8", errors="replace")
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                if not lines:
                    continue
                last_line = lines[-1]
                parts = [part.strip() for part in last_line.split(",")]
                if len(parts) > 5 and parts[5].upper() == "R":
                    return content[-2000:]
    except (OSError, ValueError, zipfile.BadZipFile):
        logger.warning("CDSL response archive could not be inspected")
    return ""


def _set_cdsl_push_state(client):
    """Mark CDSL complete only after upload, closed status, and download."""
    client.cdsl_push = True
    client.cdsl_push_at = timezone.localtime()
    client.save(update_fields=["cdsl_push", "cdsl_push_at"])
    logger.info(
        "CDSL push state saved: clientcode=%s pushed_at=%s",
        client.clientcode,
        client.cdsl_push_at,
    )


def _update_cdsl_upload(upload, status, response, acknowledgment_id=None):
    upload.status = status
    upload.response = response or {}
    if acknowledgment_id:
        upload.acknowledgment_id = _text(acknowledgment_id)
    update_fields = ["status", "response", "updated_at"]
    if acknowledgment_id:
        update_fields.append("acknowledgment_id")
    upload.save(update_fields=update_fields)
    logger.info(
        "CDSL upload state saved: upload_id=%s status=%s stage=%s",
        upload.id,
        status,
        _text((response or {}).get("stage")),
    )


def _cdsl_links(request, upload):
    return {
        "cdsl_request_url": _file_url(request, upload.id, "request"),
        "cdsl_archive_url": _file_url(request, upload.id, "archive"),
        "cdsl_response_url": _file_url(request, upload.id, "response"),
        "cdsl_log_url": _file_url(request, upload.id, "log"),
        "cdsl_response_archive_url": _file_url(request, upload.id, "response_archive"),
    }


def _file_url(request, upload_id, kind):
    return request.build_absolute_uri(
        f"/api/cdsl_upload/{upload_id}/file/{quote(kind, safe='')}/"
    )


def _next_batch(credential):
    with transaction.atomic():
        locked = CdslCredentials.objects.select_for_update().get(pk=credential.pk)
        next_value = (int(locked.last_batch or 0) + 1) % 100000
        locked.last_batch = next_value
        locked.save(update_fields=["last_batch", "updated_at"])
    return str(next_value).zfill(5)


def _fetch_client(clientcode, company_user):
    return UserDetails.objects.filter(
        clientcode=clientcode,
        user=company_user,
    ).first()


def _authorized_cdsl_upload(request, upload_id):
    """Return an upload only when the requesting user may access it."""
    upload = CdslUpload.objects.select_related("client", "user").filter(id=upload_id).first()
    if upload is None:
        return None
    if (
        request.user.is_staff
        or request.user.is_superuser
        or upload.user_id == request.user.id
        or upload.client.user_id == request.user.id
    ):
        return upload
    logger.warning(
        "Rejected unauthorized CDSL upload request: upload_id=%s user_id=%s",
        upload_id,
        getattr(request.user, "id", None),
    )
    return None


@api_view(["GET", "POST"])
def cdsl_credentials_view(request):
    """Read or save CDSL credentials for the selected company."""
    company_user = _requested_company_user(request)
    if company_user is None:
        return Response({"error": "Company not found."}, status=404)

    credential_fields = _cdsl_credential_fields()
    credential = CdslCredentials.objects.filter(user=company_user).first()
    if request.method == "GET":
        logger.debug(
            "CDSL credentials loaded: company_user_id=%s configured=%s",
            company_user.id,
            bool(credential),
        )
        return Response({
            "user_id": company_user.id,
            "company": company_user.username,
            "credentials": {
                field: _text(getattr(credential, field, "")) if credential else ""
                for field in credential_fields
            },
        })

    values = {
        field: _text(request.data.get(field, ""))
        for field in credential_fields
    }
    if credential:
        if not values["Password"]:
            values.pop("Password")
        if not values["AES_key"]:
            values.pop("AES_key")
    logger.info(
        "Saving CDSL credentials: company_user_id=%s dpid=%s fields=%s",
        company_user.id,
        values.get("DPID", _text(getattr(credential, "DPID", ""))),
        sorted(values),
    )
    credential, _ = CdslCredentials.objects.update_or_create(
        user=company_user,
        defaults=values,
    )
    return Response({
        "success": True,
        "id": credential.id,
        "user_id": company_user.id,
        "company": company_user.username,
        "credentials": {
            field: _text(getattr(credential, field, ""))
            for field in credential_fields
        },
    })


@api_view(["POST"])
def cdsl_ucc_modify(request, clientcode):
    """Run the resumable CDSL upload -> status -> download workflow.

    The first click creates and uploads the archive.  Later clicks resume from
    the saved upload stage, poll CDSL until the status is closed, and only
    then download the response file.  A failed retry never uploads the same
    archive again unless the first upload stage itself failed.
    """
    clientcode = _text(clientcode)
    if not _safe_clientcode(clientcode):
        return Response({"success": False, "msg": "Invalid client code."}, status=400)

    client = None
    upload = None
    current_stage = CDSL_STAGE_UPLOAD
    provider_response = None
    try:
        company_user = _requested_company_user(request)
        if company_user is None:
            return Response({"success": False, "msg": "Company not found."}, status=404)

        client = _fetch_client(clientcode, company_user)
        if client is None:
            return Response({"success": False, "msg": "Client not found."}, status=404)

        api_not_selected = reject_if_api_not_selected(client, "CDSL")
        if api_not_selected:
            return api_not_selected

        if client.cdsl_push and client.cdsl_push_at:
            message = "CDSL has already been pushed for this client."
            return Response(
                {
                    "success": False,
                    "already_pushed": True,
                    "message": message,
                    "msg": message,
                },
                status=409,
            )

        order_blocked = reject_if_provider_order_blocked(client, "CDSL")
        if order_blocked:
            return order_blocked

        credential = CdslCredentials.objects.filter(user=company_user).first()
        if credential is None:
            raise CdslError("CDSL credentials are not configured.")
        missing_credentials = [
            field for field in ("DPID", "UserID", "Password", "AES_key")
            if not _text(getattr(credential, field, ""))
        ]
        if missing_credentials:
            raise CdslError(
                "CDSL credentials are not configured completely: "
                + ", ".join(missing_credentials)
                + "."
            )
        _cdsl_key(credential.AES_key)
        urls = _cdsl_urls()

        previous_upload = CdslUpload.objects.filter(client=client).first()
        previous_response = previous_upload.response if previous_upload else {}
        previous_stage = _text(previous_response.get("stage"))
        if previous_upload and previous_stage in {CDSL_STAGE_STATUS, CDSL_STAGE_DOWNLOAD}:
            upload = previous_upload
            acknowledgment_id = _text(upload.acknowledgment_id)
            if not acknowledgment_id:
                raise CdslError("CDSL acknowledgment ID is missing; upload the file again.")
            logger.info(
                "CDSL workflow resumed: clientcode=%s upload_id=%s stage=%s acknowledgment_id=%s",
                clientcode,
                upload.id,
                previous_stage,
                acknowledgment_id,
            )
        else:
            previous_stage = CDSL_STAGE_UPLOAD

        if previous_stage == CDSL_STAGE_UPLOAD:
            cdsl_master = Cdsl.objects.order_by("id").first()
            if cdsl_master is None:
                logger.warning("CDSL master record is missing; using empty static defaults")
            else:
                configured_fields = sum(
                    bool(_text(getattr(cdsl_master, field, "")))
                    for field in CDSL_FIELDS
                )
                logger.info(
                    "CDSL master template loaded: id=%s configured_fields=%s total_fields=%s",
                    cdsl_master.id,
                    configured_fields,
                    len(CDSL_FIELDS),
                )

            batch_number = _next_batch(credential)
            rows = _build_cdsl_rows(client, credential, cdsl_master, batch_number)
            csv_body = _csv_text(rows)
            csv_filename = (
                f"BO_UPLD_{_text(credential.DPID).rjust(6, '0')}_"
                f"{timezone.localtime().strftime('%Y%m%d%H%M')}_{batch_number}.csv"
            )
            initial_response = {
                "success": True,
                "status": "uploading",
                "stage": CDSL_STAGE_UPLOAD,
                "message": "CDSL request payload is being uploaded.",
                "batch_number": batch_number,
                "filename": csv_filename,
                "row_count": len(rows),
            }
            log_body = "\n".join((
                "CDSL upload log",
                f"clientcode: {clientcode}",
                f"batch_number: {batch_number}",
                f"filename: {csv_filename}",
                "status: uploading",
                f"row_count: {len(rows)}",
                f"created_at: {timezone.localtime().isoformat()}",
            )) + "\n"
            upload = CdslUpload.objects.create(
                user=request.user,
                client=client,
                batch_number=batch_number,
                filename=csv_filename,
                status="submitting",
                row_count=len(rows),
                response=initial_response,
            )
            directory = _save_cdsl_artifacts(
                clientcode,
                csv_body,
                json.dumps(initial_response, ensure_ascii=False, indent=2),
                log_body,
                csv_filename,
            )
            archive_path = directory / "request.zip"
            current_stage = CDSL_STAGE_UPLOAD
            token, auth_audit = _cdsl_authenticate(credential, urls)
            acknowledgment_id, upload_audit = _cdsl_upload_archive(
                credential,
                token,
                archive_path,
                urls,
            )
            provider_response = {"auth": auth_audit, "upload": upload_audit}
            response_data = {
                "success": True,
                "completed": False,
                "status": "uploaded",
                "stage": CDSL_STAGE_STATUS,
                "next_stage": CDSL_STAGE_STATUS,
                "message": (
                    "The file has been successfully uploaded to CDSL. "
                    "Click the CDSL button again to check the status."
                ),
                "batch_number": batch_number,
                "filename": csv_filename,
                "row_count": len(rows),
                "acknowledgment_id": acknowledgment_id,
                "provider_response": provider_response,
            }
            _update_cdsl_upload(upload, "pending", response_data, acknowledgment_id)
            _save_text(
                directory / "response.txt",
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
            )
            _save_text(directory / "log.txt", log_body + "status: uploaded\n")
            logger.info(
                "CDSL first stage completed: clientcode=%s upload_id=%s acknowledgment_id=%s",
                clientcode,
                upload.id,
                acknowledgment_id,
            )
            return Response({**response_data, "upload_id": upload.id, **_cdsl_links(request, upload)})

        def complete_download(token, stage_response):
            nonlocal current_stage
            current_stage = CDSL_STAGE_DOWNLOAD
            download_data, download_audit = _cdsl_download_response(
                credential,
                token,
                upload.filename,
                urls,
            )
            stage_response["download"] = download_audit
            response_archive = _cdsl_response_archive(download_data)
            rejection = _cdsl_validate_response_archive(response_archive)
            if rejection:
                raise CdslProviderError(
                    f"CDSL response file rejected the record: {rejection}",
                    download_data,
                    CDSL_STAGE_DOWNLOAD,
                )

            final_data = {
                "success": True,
                "completed": True,
                "status": "accepted",
                "stage": CDSL_STAGE_DOWNLOAD,
                "message": "CDSL upload, closed status, and response download completed successfully.",
                "acknowledgment_id": _text(upload.acknowledgment_id),
                "provider_response": stage_response,
            }
            _update_cdsl_upload(upload, "accepted", final_data)
            directory = settings.BASE_DIR / "static" / "cdsl_data" / _safe_clientcode(clientcode)
            _save_text(directory / "response.txt", json.dumps(final_data, ensure_ascii=False, indent=2, default=str))
            _save_text(directory / "log.txt", "CDSL status: closed\nCDSL response: accepted\n")
            if response_archive:
                _save_binary(directory / "response.zip", response_archive)
            _set_cdsl_push_state(client)
            logger.info(
                "CDSL workflow completed: clientcode=%s upload_id=%s acknowledgment_id=%s",
                clientcode,
                upload.id,
                upload.acknowledgment_id,
            )
            return Response({
                **final_data,
                "upload_id": upload.id,
                "cdsl_push": True,
                "cdsl_push_at": client.cdsl_push_at,
                **_cdsl_links(request, upload),
            })

        if previous_stage == CDSL_STAGE_DOWNLOAD:
            current_stage = CDSL_STAGE_DOWNLOAD
            token, auth_audit = _cdsl_authenticate(credential, urls)
            provider_response = {"auth": auth_audit}
            return complete_download(token, provider_response)

        current_stage = CDSL_STAGE_STATUS
        token, auth_audit = _cdsl_authenticate(credential, urls)
        status_text, status_audit = _cdsl_status(
            credential,
            token,
            _text(upload.acknowledgment_id),
            urls,
        )
        provider_response = {"auth": auth_audit, "status": status_audit}
        status_data = {
            "success": True,
            "completed": False,
            "status": status_text,
            "stage": CDSL_STAGE_STATUS,
            "next_stage": CDSL_STAGE_STATUS,
            "message": f"CDSL status: {status_text}. Click again to check again.",
            "acknowledgment_id": _text(upload.acknowledgment_id),
            "provider_response": provider_response,
        }
        if not _cdsl_status_is_closed(status_text):
            _update_cdsl_upload(upload, "pending", status_data)
            directory = settings.BASE_DIR / "static" / "cdsl_data" / _safe_clientcode(clientcode)
            _save_text(directory / "response.txt", json.dumps(status_data, ensure_ascii=False, indent=2, default=str))
            _save_text(directory / "log.txt", f"CDSL status: {status_text}\n")
            logger.info(
                "CDSL status is not closed; third API skipped: clientcode=%s status=%s",
                clientcode,
                status_text,
            )
            return Response({**status_data, "upload_id": upload.id, **_cdsl_links(request, upload)}, status=202)

        return complete_download(token, provider_response)
    except CdslProviderError as exc:
        provider_response = exc.provider_response or provider_response
        # Authentication is an internal prerequisite of the current stage;
        # retrying a failed status/download authentication must not restart
        # the already accepted upload.
        if exc.stage and exc.stage != "auth":
            current_stage = exc.stage
        logger.warning(
            "CDSL provider error: clientcode=%s stage=%s error=%s",
            clientcode,
            current_stage,
            exc,
        )
        error_body = {
            "success": False,
            "completed": False,
            "stage": current_stage,
            "error": _text(exc),
            "message": _text(exc),
            "msg": _text(exc),
            "provider_response": provider_response,
        }
        if upload is not None:
            _update_cdsl_upload(upload, "failed", error_body)
        if client is not None:
            try:
                _save_cdsl_error_artifact(clientcode, exc, provider_response, current_stage)
            except (OSError, ValueError):
                logger.exception("Unable to save CDSL provider error artifact: clientcode=%s", clientcode)
        return Response({
            **error_body,
            "upload_id": upload.id if upload else None,
            **(_cdsl_links(request, upload) if upload else {}),
        }, status=502)
    except requests.RequestException as exc:
        logger.exception("CDSL provider connection failed: clientcode=%s stage=%s", clientcode, current_stage)
        error_body = {
            "success": False,
            "completed": False,
            "stage": current_stage,
            "error": str(exc),
            "message": f"Unable to connect to CDSL {current_stage} API: {exc}",
            "msg": f"Unable to connect to CDSL {current_stage} API: {exc}",
        }
        if upload is not None:
            _update_cdsl_upload(upload, "failed", error_body)
        if client is not None:
            try:
                _save_cdsl_error_artifact(clientcode, error_body["message"], provider_response, current_stage)
            except (OSError, ValueError):
                logger.exception("Unable to save CDSL connection error artifact: clientcode=%s", clientcode)
        return Response({
            **error_body,
            "upload_id": upload.id if upload else None,
            **(_cdsl_links(request, upload) if upload else {}),
        }, status=502)
    except CdslError as exc:
        logger.warning("CDSL workflow validation failed: clientcode=%s error=%s", clientcode, exc)
        error_message = _text(exc)
        error_body = {
            "success": False,
            "completed": False,
            "stage": current_stage,
            "error": error_message,
            "message": error_message,
            "msg": error_message,
        }
        if client is not None:
            try:
                if upload is not None:
                    _update_cdsl_upload(upload, "failed", error_body)
                _save_cdsl_error_artifact(clientcode, error_message, provider_response, current_stage)
            except (DatabaseError, OSError, ValueError):
                logger.exception("Unable to save CDSL error response: clientcode=%s", clientcode)
        return Response({
            **error_body,
            "upload_id": upload.id if upload else None,
            **(_cdsl_links(request, upload) if upload else {}),
        }, status=400)
    except (DatabaseError, OSError, ValueError) as exc:
        logger.exception("CDSL workflow failed: clientcode=%s stage=%s", clientcode, current_stage)
        error_message = _text(exc)
        error_body = {
            "success": False,
            "completed": False,
            "stage": current_stage,
            "error": error_message,
            "message": error_message,
            "msg": error_message,
        }
        if client is not None:
            try:
                if upload is not None:
                    _update_cdsl_upload(upload, "failed", error_body)
                _save_cdsl_error_artifact(clientcode, error_message, provider_response, current_stage)
            except (DatabaseError, OSError, ValueError):
                logger.exception("Unable to save CDSL error response: clientcode=%s", clientcode)
        return Response({
            **error_body,
            "upload_id": upload.id if upload else None,
            **(_cdsl_links(request, upload) if upload else {}),
        }, status=500)


@api_view(["GET"])
def cdsl_file(request, upload_id, kind):
    """Serve a CDSL request, response, or archive to an authorized user."""
    file_info = CDSL_FILE_KINDS.get(_text(kind).casefold())
    if file_info is None:
        raise Http404("CDSL file not found.")

    upload = _authorized_cdsl_upload(request, upload_id)
    if upload is None:
        raise Http404("CDSL file not found.")

    filename, content_type = file_info
    path = settings.BASE_DIR / "static" / "cdsl_data" / _safe_clientcode(upload.client.clientcode) / filename
    if not path.is_file():
        logger.warning("CDSL artifact missing: upload_id=%s filename=%s", upload_id, filename)
        raise Http404("CDSL file not found.")
    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=filename,
        content_type=content_type,
    )


@api_view(["GET"])
def cdsl_upload_status(request, upload_id):
    """Return the saved status and response for an authorized CDSL upload."""
    upload = _authorized_cdsl_upload(request, upload_id)
    if upload is None:
        raise Http404("CDSL upload not found.")

    logger.debug(
        "CDSL upload status loaded: upload_id=%s clientcode=%s status=%s",
        upload.id,
        upload.client.clientcode,
        upload.status,
    )
    return Response({
        "id": upload.id,
        "clientcode": upload.client.clientcode,
        "status": upload.status,
        "batch_number": upload.batch_number,
        "filename": upload.filename,
        "acknowledgment_id": upload.acknowledgment_id,
        "row_count": upload.row_count,
        "response": upload.response or {},
        **_cdsl_links(request, upload),
        "created_at": timezone.localtime(upload.created_at).isoformat() if upload.created_at else "",
        "updated_at": timezone.localtime(upload.updated_at).isoformat() if upload.updated_at else "",
    })
