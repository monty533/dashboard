import base64
import binascii
import datetime as dt
import io
import json
import logging
import random
import re
import string
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.db import DatabaseError
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Nsdl,
    NsdlAccountTypeMaster,
    NsdlCountryMaster,
    NsdlCredentials,
    NsdlGenderMaster,
    NsdlIncomeRangeMaster,
    NsdlOccupationMaster,
    NsdlRelationMaster,
    NsdlStateCodeMaster,
    UserDetails,
)
from .views import _requested_company_user
from .push_tracking import (
    reject_if_already_pushed,
    reject_if_api_not_selected,
    reject_if_provider_order_blocked,
)

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - dependency is declared in requirements.txt
    Image = None
    UnidentifiedImageError = OSError


logger = logging.getLogger(__name__)


def _set_nsdl_push_state(client, state):
    """Store only the successful NSDL time; keep nsdl_push as permission."""
    if not state:
        return
    try:
        client.nsdl_push_at = timezone.localtime()
        client.save(update_fields=['nsdl_push_at'])
        logger.info(
            'NSDL push state saved: clientcode=%s pushed_at=%s',
            client.clientcode,
            client.nsdl_push_at,
        )
    except DatabaseError:
        logger.exception('Unable to save NSDL push state: clientcode=%s', client.clientcode)

NSDL_LIVE_URL = "https://eservices.nsdl.com/client-service/v4/instaDemat/{requesterid}/order"
NSDL_UAT_URL = "https://eservices-test.nsdl.com/client-service/v4/instaDemat/{requesterid}/order"
NSDL_SIGNING_BASE_URL = "https://115.112.16.66"
NSDL_TRANSACTION_TYPE = "IDD"
NSDL_SIGNATURE_LIMIT_BYTES = 60 * 1024
NSDL_SOURCE_LIMIT_BYTES = 5 * 1024 * 1024

NSDL_CREDENTIAL_FIELDS = (
    "requesterid",
    "certificate_file_name",
    "private_key_file_password",
    "private_key_filename",
    "ddpi_id",
)

NSDL_STATIC_FIELDS = (
    "panFlag",
    "eStatement",
    "familyMobileFlag",
    "familyEmailFlag",
)

DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%Y%m%d",
    "%d%m%Y",
    "%m/%d/%Y",
)


class NsdlError(ValueError):
    """A client-data or NSDL configuration error safe to return to the UI."""


def _text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _yes(value):
    return _text(value).casefold() in {"1", "true", "yes", "y", "p", "primary"}


def _record_error(errors, message, *args):
    """Log an input/configuration error and keep it with the current request."""
    logger.error(message, *args)
    if errors is None:
        return
    try:
        errors.append(message % args if args else message)
    except (TypeError, ValueError):
        errors.append(" ".join([message, *(str(arg) for arg in args)]))


def _normalized_label(value):
    value = _text(value).casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = []
    for token in value.split():
        if token == "lacs":
            token = "lac"
        elif token == "lakhs":
            token = "lakh"
        tokens.append(token)
    return " ".join(tokens)


def _getter(record):
    if isinstance(record, dict):
        values = {str(key).casefold(): value for key, value in record.items()}
    else:
        values = {
            field.name.casefold(): getattr(record, field.name, "")
            for field in record._meta.concrete_fields
        }

    def get(*names, default=""):
        for name in names:
            key = str(name).casefold()
            if key in values:
                value = _text(values[key])
                if value:
                    return value
        return default

    return get


def _credential_value(credential, field):
    if isinstance(credential, dict):
        return _text(credential.get(field))
    return _text(getattr(credential, field, ""))


def _fetch_nsdl_credentials(company_user):
    """Load only the NSDL credential columns configured for this company."""
    credential = NsdlCredentials.objects.only(*NSDL_CREDENTIAL_FIELDS).filter(
        user=company_user,
    ).first()
    logger.info(
        "NSDL credentials lookup: company_user_id=%s configured=%s",
        company_user.id,
        bool(credential),
    )
    return credential


def _fetch_nsdl_defaults(errors=None):
    """Load the static NSDL payload values configured in the nsdl table."""
    try:
        defaults = Nsdl.objects.order_by("id").values(*NSDL_STATIC_FIELDS).first() or {}
        if defaults:
            logger.info(
                "Loaded NSDL static defaults: configured_fields=%s",
                [
                    field
                    for field in NSDL_STATIC_FIELDS
                    if _text(defaults.get(field))
                ],
            )
        else:
            _record_error(errors, "No NSDL static defaults row found")
        return defaults
    except DatabaseError:
        logger.exception("Unable to read static NSDL payload values")
        _record_error(errors, "Unable to read static NSDL payload values")
        return {}


def _parse_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value

    value = _text(value)
    if not value:
        return None

    match = re.search(r"\d{1,4}[-/]\w{1,3}[-/]\d{1,4}|\d{8}", value)
    candidate = match.group(0) if match else value.split(" ", 1)[0]
    for date_format in DATE_FORMATS:
        try:
            return dt.datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    return None


def _is_minor(parsed_dob):
    today = timezone.localdate()
    age = today.year - parsed_dob.year - (
        (today.month, today.day) < (parsed_dob.month, parsed_dob.day)
    )
    return age < 18


def _split_address(*parts, line_length=54, line_count=4):
    value = " ".join(_text(part) for part in parts if _text(part))
    value = re.sub(r"[^a-zA-Z0-9\s]", " ", value)
    value = " ".join(value.split())
    if not value:
        return [""] * line_count

    lines = []
    remaining = value
    while remaining and len(lines) < line_count:
        if len(remaining) <= line_length:
            lines.append(remaining)
            remaining = ""
            break

        split_at = remaining.rfind(" ", 0, line_length + 1)
        if split_at <= 0:
            split_at = line_length
        lines.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    # Payload generation is intentionally permissive for now.  NSDL can
    # reject an overlong address later, but a missing/truncated line should
    # not prevent us from producing the same kind of request artifact as NSE
    # and BSE do.
    if remaining and lines:
        lines[-1] = f"{lines[-1]} {remaining}"[:line_length].strip()
    return lines + [""] * (line_count - len(lines))


def _master_code(model, label_field, code_field, value, errors=None):
    raw_value = _text(value)
    if not raw_value:
        return ""

    try:
        exact_code = model.objects.filter(
            **{f"{label_field}__iexact": raw_value}
        ).values_list(code_field, flat=True).first()
        if _text(exact_code):
            code = _text(exact_code)
            logger.info(
                "NSDL master mapping resolved: table=%s code=%s match=exact",
                model._meta.db_table,
                code,
            )
            return code

        normalized = _normalized_label(raw_value)
        for label, code in model.objects.values_list(label_field, code_field):
            if _normalized_label(label) == normalized and _text(code):
                code = _text(code)
                logger.info(
                    "NSDL master mapping resolved: table=%s code=%s match=normalized",
                    model._meta.db_table,
                    code,
                )
                return code
    except DatabaseError:
        logger.exception("Unable to read %s master data", model._meta.db_table)
        _record_error(
            errors,
            "Unable to read %s master data",
            model._meta.db_table,
        )
    return ""


def _state_code(value, errors=None):
    value = _text(value)
    if not value:
        return ""
    if re.fullmatch(r"\d{1,2}", value):
        return str(int(value))

    code = _master_code(
        NsdlStateCodeMaster,
        "state_name",
        "state_code",
        value,
        errors,
    )
    if code:
        return str(int(code)) if code.isdigit() else code
    _record_error(errors, "NSDL state code not found in master table: %s", value)
    return value


def _income_code(value, errors=None):
    raw_value = _text(value)
    if not raw_value:
        return ""
    if re.fullmatch(r"0[1-5]", raw_value):
        return raw_value
    code = _master_code(
        NsdlIncomeRangeMaster,
        "income_range",
        "income_code",
        raw_value,
        errors,
    )
    # NSDL income master values are provider codes such as 01 through 05.
    # Accept the configured master code as-is.
    if code:
        logger.info(
            "NSDL income code resolved from master: mapped=%s code=%s",
            True,
            code,
        )
        return code
    logger.info("NSDL income code resolved from master: mapped=%s", False)
    _record_error(
        errors,
        "NSDL income code not found in master table: %s",
        raw_value,
    )
    return raw_value


def _occupation_code(value, errors=None):
    raw_value = _text(value)
    if not raw_value:
        return ""
    if re.fullmatch(r"\d{1,2}", raw_value):
        return raw_value
    code = _master_code(
        NsdlOccupationMaster,
        "occupation_name",
        "occupation_code",
        raw_value,
        errors,
    )
    if not code:
        _record_error(
            errors,
            "NSDL occupation code not found in master table: %s",
            raw_value,
        )
        return raw_value
    return code


def _relation_code(value, nominee_number, errors=None):
    raw_value = _text(value)
    if not raw_value:
        return ""
    if re.fullmatch(r"(?:0\d|1\d)", raw_value):
        return raw_value
    code = _master_code(
        NsdlRelationMaster,
        "relation_name",
        "relation_code",
        raw_value,
        errors,
    )
    if not code:
        _record_error(
            errors,
            "NSDL relationship code not found in master table: nominee=%s value=%s",
            nominee_number,
            raw_value,
        )
        return raw_value
    return code


def _gender_code(value, errors=None):
    code = _master_code(
        NsdlGenderMaster,
        "gender",
        "gender_code",
        value,
        errors,
    )
    if code:
        return code

    _record_error(errors, "NSDL gender code not found in master table: %s", value)
    return ""


def _country_code(value, errors=None):
    code = _master_code(
        NsdlCountryMaster,
        "country",
        "country_code",
        value,
        errors,
    )
    if code:
        return code

    _record_error(errors, "Country code not found.")
    return _text(value)


def _address(parts, city, state, country, pincode, address_type, errors=None):
    line1, line2, line3, line4 = _split_address(*parts)
    zipcode = re.sub(r"\D", "", _text(pincode))
    return {
        "addressLine1": line1,
        "addressLine2": line2,
        "addressLine3": line3,
        "addressLine4": line4,
        "addressType": _text(address_type),
        "city": _text(city)[:45],
        "countrycode": _country_code(country, errors),
        "statecode": _state_code(state, errors),
        "zipcode": zipcode,
    }


def _bank_address(parts, pincode):
    line1, line2, line3, line4 = _split_address(*parts)
    zipcode = re.sub(r"\D", "", _text(pincode))
    return {
        "addressType": 2,
        "addressLine1": line1,
        "addressLine2": line2,
        "addressLine3": line3,
        "addressLine4": line4,
        "zipcode": zipcode,
    }


def _account_type_code(value, errors=None):
    code = _master_code(
        NsdlAccountTypeMaster,
        "account_type",
        "account_code",
        value,
        errors,
    )
    if code:
        return code

    _record_error(
        errors,
        "NSDL account type code not found in master table: %s",
        value,
    )
    return ""


def _empty_guardian_address():
    return {
        "addressLine1": "",
        "addressLine2": "",
        "addressLine3": "",
        "addressLine4": "",
        "addressType": "",
        "city": "",
        "countrycode": "",
        "statecode": "",
        "zipcode": "",
    }


def _build_nominees(get, errors=None):
    if not _yes(get("nominee_check")):
        logger.info("NSDL nominee payload disabled: nominee_check is not yes")
        return []

    nominees = []
    guardianFlag = get("guardianFlag")
    for number in (1, 2, 3):
        name = get(f"nominee{number}_name")
        dob_value = get(f"nominee{number}_dob")
        nominee_values = (
            name,
            dob_value,
            get(f"nominee{number}_pan"),
            get(f"nominee{number}_relation"),
            get(f"nominee{number}_address1"),
            get(f"nominee{number}_mobile"),
            get(f"nominee{number}_email"),
        )
        if not any(nominee_values):
            logger.debug("NSDL nominee slot is empty: slot=%s", number)
            continue

        parsed_dob = _parse_date(dob_value)
        pan = get(f"nominee{number}_pan").upper()

        sequence = len(nominees) + 1
        nominee_address_types = {1: "3", 2: "7", 3: "9"}
        nominees.append({
            "seqNo": str(sequence),
            "nomineeName": name,
            "nomineeShare": "",
            "dob": parsed_dob.strftime("%Y%m%d") if parsed_dob else dob_value,
            "minor": "Y" if parsed_dob and _is_minor(parsed_dob) else "N",
            "relationWithNominee": _relation_code(
                get(f"nominee{number}_relation"),
                number,
                errors,
            ),
            "nomineeMobileNum": get(f"nominee{number}_mobile"),
            "nomineeEmailId": get(f"nominee{number}_email"),
            "nomineeIdentificationDtls": {
                "pan": pan,
                "aadhar": "",
                "dematAccId": "",
                "savingBankAccNo": "",
            },
            "nomineeAddress": _address(
                (
                    get(f"nominee{number}_address1"),
                    get(f"nominee{number}_address2"),
                ),
                get(f"nominee{number}_city"),
                get(f"nominee{number}_state"),
                get(f"nominee{number}_country"),
                get(f"nominee{number}_pincode"),
                nominee_address_types[sequence],
                errors,
            ),
            "guardianFlag": guardianFlag,
            "guardianName": "",
            "guardianRelationship": "",
            "guardianMobileNum": "",
            "guardianEmailId": "",
            "guardianIdentificationDtls": {
                "pan": "",
                "aadhar": "",
                "dematAccId": "",
                "savingBankAccNo": "",
            },
            "guardianAddress": _empty_guardian_address(),
        })
        logger.debug(
            "NSDL nominee slot prepared: slot=%s sequence=%s minor=%s",
            number,
            sequence,
            nominees[-1]["minor"],
        )

    logger.info("NSDL nominee payload prepared: count=%s", len(nominees))
    return nominees


def _read_limited_response(response):
    data = bytearray()
    for chunk in response.iter_content(64 * 1024):
        if not chunk:
            continue
        data.extend(chunk)
        if len(data) > NSDL_SOURCE_LIMIT_BYTES:
            raise NsdlError("Signature image is larger than 5 MB.")
    return bytes(data)


def _path_inside_base_dir(value, label):
    candidate = Path(_text(value))
    if not candidate.is_absolute():
        candidate = Path(settings.BASE_DIR) / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise NsdlError(f"{label} was not found.") from exc

    base_dir = Path(settings.BASE_DIR).resolve()
    if resolved != base_dir and base_dir not in resolved.parents:
        raise NsdlError(f"{label} must be stored inside the backend directory.")
    if not resolved.is_file():
        raise NsdlError(f"{label} was not found.")
    return resolved


def _signature_source_bytes(value):
    value = _text(value)
    if not value:
        raise NsdlError("Signature file is required for NSDL.")

    if value.startswith("data:"):
        try:
            _, encoded = value.split(",", 1)
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise NsdlError("Signature contains invalid base64 data.") from exc
    elif urlparse(value).scheme in {"http", "https"}:
        try:
            with requests.get(value, stream=True, timeout=15) as response:
                response.raise_for_status()
                data = _read_limited_response(response)
        except requests.RequestException as exc:
            raise NsdlError("Signature file could not be downloaded.") from exc
    else:
        path = _path_inside_base_dir(value, "Signature file")
        try:
            if path.stat().st_size > NSDL_SOURCE_LIMIT_BYTES:
                raise NsdlError("Signature image is larger than 5 MB.")
            data = path.read_bytes()
        except OSError as exc:
            raise NsdlError("Signature file could not be read.") from exc

    if not data:
        raise NsdlError("Signature file is empty.")
    if len(data) > NSDL_SOURCE_LIMIT_BYTES:
        raise NsdlError("Signature image is larger than 5 MB.")
    return data


def _flatten_transparency(image):
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _compress_signature(data):
    if Image is None:
        raise NsdlError("Pillow is required to prepare the NSDL signature image.")

    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = _flatten_transparency(source)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise NsdlError("Signature file is not a valid image.") from exc

    current = image
    for _ in range(8):
        for quality in (90, 80, 70, 60, 50, 40, 30, 20, 10):
            output = io.BytesIO()
            current.save(output, format="JPEG", quality=quality, optimize=True)
            encoded = output.getvalue()
            if len(encoded) <= NSDL_SIGNATURE_LIMIT_BYTES:
                return encoded

        width = max(1, int(current.width * 0.85))
        height = max(1, int(current.height * 0.85))
        if (width, height) == current.size:
            break
        current = current.resize((width, height), Image.Resampling.LANCZOS)

    raise NsdlError("Signature image could not be compressed below 60 KB.")


def _signature_base64(value, errors=None):
    if not _text(value):
        return ""
    try:
        source = _signature_source_bytes(value)
        compressed = _compress_signature(source)
        encoded = base64.b64encode(compressed).decode("ascii")
        logger.info(
            "NSDL signature converted: source_bytes=%s compressed_bytes=%s",
            len(source),
            len(compressed),
        )
        return encoded
    except NsdlError as exc:
        # Keep payload generation non-blocking until NSDL validation is
        # explicitly enabled.  The source value is retained for inspection
        # instead of rejecting the complete payload.
        _record_error(errors, "NSDL signature was not converted: %s", exc)
        return _text(value)


def _resolve_client_id(get, requested_client_id=""):
    candidates = (
        _text(requested_client_id),
        get("dpid")[8:] if get("dpid").upper().startswith("IN") else "",
        re.sub(r"\D", "", get("clientcode"))[-8:],
    )
    return next((value for value in candidates if value), "")


def _build_nsdl_payload(
    client,
    credential,
    requested_client_id="",
    nsdl_defaults=None,
    errors=None,
):
    get = _getter(client)
    static_get = _getter(nsdl_defaults or {})

    # Requester ID is required by the live NSDL service, but it is not needed
    # to prepare a local payload.  Keep it empty when credentials are not yet
    # configured so the dashboard can generate the request artifact first.
    requesterid = _credential_value(credential, "requesterid")

    client_id = _resolve_client_id(get, requested_client_id)
    nominee_enabled = _yes(get("nominee_check"))
    nominees = _build_nominees(get, errors)
    logger.info(
        "Building NSDL payload: clientcode=%s nominee_enabled=%s nominee_count=%s static_defaults=%s",
        get("clientcode", default="<unknown>"),
        nominee_enabled,
        len(nominees),
        bool(nsdl_defaults),
    )
    correspondence_address = _address(
        (get("addressline1"), get("addressline2"), get("addressline3")),
        get("aadhaar_dist", "aadhar_dist", "adhar_dist", "city"),
        get("aadhaar_state", "aadhar_state", "adhar_state", "state"),
        get("aadhaar_country", "aadhar_country", "adhar_country", "country"),
        get("aadhaar_pincode", "aadhar_pincode", "adhar_pincode", "pincode"),
        "1",
        errors,
    )

    permanent_parts = (
        get("aadhaar_house", "aadhar_house", "adhar_house"),
        get("aadhaar_address", "aadhar_address", "adhar_address"),
    )
    if any(permanent_parts):
        permanent_address = _address(
            permanent_parts,
            get("aadhaar_dist", "aadhar_dist", "adhar_dist", "city"),
            get("aadhaar_state", "aadhar_state", "adhar_state", "state"),
            get("aadhaar_country", "aadhar_country", "adhar_country", "country"),
            get("aadhaar_pincode", "aadhar_pincode", "adhar_pincode", "pincode"),
            "4",
            errors,
        )
    else:
        permanent_address = {**correspondence_address}

    name = get("aadhaar_name", "aadhar_name", "adhar_name", "name")
    parsed_dob = _parse_date(get("dob", "aadhaar_dob", "aadhar_dob", "adhar_dob"))
    dob = (
        parsed_dob.strftime("%Y%m%d")
        if parsed_dob
        else get("dob", "aadhaar_dob", "aadhar_dob", "adhar_dob")
    )
    gender = _gender_code(get("aadhaar_gender", "aadhar_gender", "adhar_gender", "gender"), errors)
    ddpi_id = (
        _credential_value(credential, "ddpi_id")
        if _yes(get("isdppoa"))
        else ""
    )
    bank_address = _bank_address(
        (get("bankaddress"), get("branchname")),
        get("aadhaar_pincode", "pincode"),
    )
    bank_account_number = re.sub(r"\s", "", get("bankaccountnumber"))
    bank_name = get("bankname")
    bank_account_type = _account_type_code(get("accounttype"), errors)
    bank_ifsc = get("ifsc").upper()
    bank_micr = get("micr")
    income_code = _income_code(get("annual_income"), errors)

    additional_bene_details = {
        "familyMobileFlag": static_get("familyMobileFlag"),
        "familyEmailFlag": static_get("familyEmailFlag"),
        "occupation": _occupation_code(get("occupation"), errors),
        "fatherOrHusbandName": get(
            "fathername",
            "aadhaar_fathername",
            "aadhar_fathername",
            "adhar_fathername",
        )[:45],
        "dpId": requesterid,
        "clientId": client_id,
    }
    if nominee_enabled:
        additional_bene_details.update({
            "nominationOption": "Y" if nominees else "N",
            "sharePercentEqually": "Y" if nominees else "N",
            "numOfNominees": len(nominees) if nominees else "",
            "listOfNominees": nominees,
        })

    logger.info(
        "NSDL payload fields prepared: clientcode=%s has_name=%s has_pan=%s "
        "has_country=%s has_state=%s has_income=%s has_signature=%s",
        get("clientcode", default="<unknown>"),
        bool(name),
        bool(get("pan")),
        bool(correspondence_address["countrycode"]),
        bool(correspondence_address["statecode"]),
        bool(income_code),
        bool(get("uploadsignature")),
    )

    payload = {
        "instr": {
            "beneficiaryDetails": {
                "primaryBeneficiary": {
                    "name": name[:135],
                    "shortName": name[:16],
                    "pan": get("pan").upper(),
                    "panFlag": static_get("panFlag"),
                    "grossAnnualIncome": income_code,
                    "dob": dob,
                    "gender": gender,
                    "mobile": re.sub(r"\D", "", get("mobile")),
                    "email": get("email")[:50],
                    "aadhar": re.sub(r"\D", "", get("aadhaar_no", "aadhar_no", "adhar_no")),
                    "ddpiid": ddpi_id,
                    "eStatement": static_get("eStatement"),
                    "beneficiaryCoresAddress": correspondence_address,
                    "beneficiaryPermAddress": permanent_address,
                    "signature": _signature_base64(
                        get("uploadsignature"),
                        errors,
                    ),
                },
                "additionalBeneDetails": additional_bene_details,
            },
            "bankDetails": {
                "accountNumber": re.sub(r"\s", "", bank_account_number),
                "bankName": bank_name[:100],
                "accountType": bank_account_type,
                "ifsc": bank_ifsc,
                "micr": bank_micr,
                "bankAddress": bank_address,
            },
        }
    }
    return payload, client_id


def _safe_clientcode(clientcode):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", _text(clientcode))[:80]


def _artifact_path(clientcode, kind):
    directory = Path(settings.BASE_DIR) / "static" / "nsdl_data" / _safe_clientcode(clientcode)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"nsdl_{kind}.txt"


def _save_artifact(clientcode, kind, value):
    path = _artifact_path(clientcode, kind)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)
    logger.info(
        "NSDL artifact saved: clientcode=%s kind=%s filename=%s",
        _safe_clientcode(clientcode),
        kind,
        path.name,
    )
    return path


def _unique_errors(errors):
    return list(dict.fromkeys(_text(error) for error in (errors or []) if _text(error)))


def _with_nsdl_errors(data, errors):
    """Attach request errors without mixing them into the provider payload."""
    existing_errors = data.get("errors", []) if isinstance(data, dict) else []
    if isinstance(existing_errors, str):
        existing_errors = [existing_errors]
    unique_errors = _unique_errors([*existing_errors, *(errors or [])])
    if not unique_errors:
        return data
    if isinstance(data, dict):
        return {**data, "errors": unique_errors}
    return {"provider_response": data, "errors": unique_errors}


def _nsdl_error_data(message, error_status="NSDL_ERROR", errors=None):
    error_message = _text(message)
    return _with_nsdl_errors({
        "success": False,
        "status": error_status,
        "error": error_message,
        "msg": error_message,
    }, [error_message, *(errors or [])])


def _save_nsdl_error_response(
    request,
    clientcode,
    company_user,
    message,
    error_status="NSDL_ERROR",
    errors=None,
):
    """Save a local/provider error so Dashboard Logs never shows stale output."""
    error_data = _nsdl_error_data(message, error_status, errors)
    try:
        _save_artifact(clientcode, "response", error_data)
        return _artifact_url(request, clientcode, "response", company_user)
    except (OSError, ValueError):
        logger.exception("Unable to save NSDL error response: clientcode=%s", clientcode)
        return ""


def _artifact_url(request, clientcode, kind, company_user):
    client_part = quote(_safe_clientcode(clientcode), safe="")
    path = f"/api/nsdl_file/{client_part}/{kind}/"
    if request.user.is_staff or request.user.is_superuser:
        path = f"{path}?user_id={company_user.id}"
    return request.build_absolute_uri(path)


def _api_url(environment, requesterid):
    configured = _text(getattr(settings, "NSDL_KYC_BASE_URL", ""))
    if configured:
        if "{requesterid}" in configured:
            return configured.format(requesterid=quote(requesterid, safe=""))
        if configured.rstrip("/").endswith("/order"):
            return configured
        return (
            f"{configured.rstrip('/')}/client-service/v4/instaDemat/"
            f"{quote(requesterid, safe='')}/order"
        )
    template = NSDL_LIVE_URL if environment == "live" else NSDL_UAT_URL
    return template.format(requesterid=quote(requesterid, safe=""))


def _request_time():
    india_timezone = dt.timezone(dt.timedelta(hours=5, minutes=30))
    value = timezone.now().astimezone(india_timezone)
    return value.strftime("%Y-%m-%dT%H:%M:%S%z")


def _request_reference():
    return "".join(random.SystemRandom().choice(string.digits) for _ in range(12))


def _deployment_file(value, label):
    candidate = Path(_text(value))
    if not candidate.is_absolute():
        candidate = Path(settings.BASE_DIR) / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise NsdlError(f"{label} was not found.") from exc
    if not resolved.is_file():
        raise NsdlError(f"{label} was not found.")
    return resolved


def _generate_digital_signature(
    credential,
    payload_json,
    request_time,
    request_reference,
):
    requesterid = _credential_value(credential, "requesterid")
    requestor = f"{requesterid}-TEST"
    jar_value = _text(getattr(settings, "NSDL_KYC_SIGNING_JAR", "")) or "enc/nsdl_file.jar"
    jar_path = _deployment_file(jar_value, "NSDL signing JAR")
    certificate_path = _path_inside_base_dir(
        _credential_value(credential, "certificate_file_name"),
        "NSDL certificate file",
    )
    private_key_path = _path_inside_base_dir(
        _credential_value(credential, "private_key_filename"),
        "NSDL private key file",
    )
    password = _credential_value(credential, "private_key_file_password")
    if not password:
        raise NsdlError("NSDL private key password is not configured.")

    signing_base = _text(
        getattr(settings, "NSDL_KYC_SIGNING_BASE_URL", NSDL_SIGNING_BASE_URL)
    ).rstrip("/")
    signing_input = (
        f"{signing_base}/client-service/v4/instaDemat/{requesterid}/order"
        f"?Transaction-Type={NSDL_TRANSACTION_TYPE}"
        f"&Requestor={requestor}"
        f"&Requestor-Id={requesterid}"
        f"&Request-Reference={request_reference}"
        f"&Request-Time={request_time}"
        f"&jsonData={payload_json}"
    )
    # The supplied NSDL signing JAR expects the same quote-free input used by
    # the source integration. The JSON sent over HTTP remains valid JSON.
    signing_input = signing_input.replace('"', "")

    logger.info("Generating NSDL digital signature for requester %s", requesterid)
    try:
        result = subprocess.run(
            [
                "java",
                "-jar",
                str(jar_path),
                signing_input,
                str(certificate_path),
                password,
                str(private_key_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=45,
        )
    except FileNotFoundError as exc:
        raise NsdlError("Java is not installed or is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise NsdlError("NSDL digital signature generation timed out.") from exc
    except subprocess.CalledProcessError as exc:
        logger.error(
            "NSDL signing JAR failed for requester %s: %s",
            requesterid,
            _text(exc.stderr)[:500],
        )
        raise NsdlError("Failed to generate the NSDL digital signature.") from exc

    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise NsdlError("NSDL signing JAR returned an empty digital signature.")
    return output_lines[-1]


def _response_error(data, fallback):
    if not isinstance(data, dict):
        return fallback
    return _text(
        data.get("errorDescription")
        or data.get("message")
        or data.get("msg")
        or data.get("error")
        or fallback
    )


def _submit_nsdl(credential, environment, payload):
    requesterid = _credential_value(credential, "requesterid")
    request_time = _request_time()
    request_reference = _request_reference()
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    digital_signature = _generate_digital_signature(
        credential,
        payload_json,
        request_time,
        request_reference,
    )
    headers = {
        "Content-Type": "application/json",
        "Digital-Signature": digital_signature,
        "Request-Reference": request_reference,
        "Request-Time": request_time,
        "Requestor-Id": requesterid,
        "Transaction-Type": NSDL_TRANSACTION_TYPE,
        "Requestor": f"{requesterid}-TEST",
    }
    url = _api_url(environment, requesterid)

    logger.info(
        "Submitting NSDL request: requester=%s environment=%s reference=%s",
        requesterid,
        environment,
        request_reference,
    )
    try:
        response = requests.post(
            url,
            headers=headers,
            data=payload_json.encode("utf-8"),
            timeout=60,
            verify=bool(getattr(settings, "NSDL_KYC_VERIFY_SSL", True)),
        )
    except requests.RequestException as exc:
        logger.exception("NSDL request failed for reference %s", request_reference)
        raise NsdlError(f"Unable to connect to the NSDL service: {exc}") from exc

    logger.info(
        "NSDL response received: reference=%s status=%s ok=%s",
        request_reference,
        response.status_code,
        response.ok,
    )

    try:
        response_data = response.json()
    except ValueError:
        logger.error(
            "NSDL response was not JSON: reference=%s status=%s",
            request_reference,
            response.status_code,
        )
        response_data = {
            "status_code": response.status_code,
            "raw_response": response.text,
            "errors": [
                f"NSDL response was not JSON: status={response.status_code}"
            ],
        }
    return response, response_data, request_reference


def _credential_response(credential):
    return {
        field: _credential_value(credential, field)
        for field in NSDL_CREDENTIAL_FIELDS
    }


@api_view(["GET", "POST"])
def nsdl_credentials_view(request):
    company_user = _requested_company_user(request)
    if company_user is None:
        return Response(
            {"error": "Company not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    credential = _fetch_nsdl_credentials(company_user)
    if request.method == "GET":
        return Response({
            "user_id": company_user.id,
            "company": company_user.username,
            "credentials": _credential_response(credential),
        })

    values = {}
    for field_name in NSDL_CREDENTIAL_FIELDS:
        value = _text(request.data.get(field_name))
        if field_name == "private_key_file_password" and not value and credential:
            value = credential.private_key_file_password
        if not value:
            return Response(
                {"error": f"{field_name} is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        max_length = NsdlCredentials._meta.get_field(field_name).max_length
        if max_length and len(value) > max_length:
            return Response(
                {"error": f"{field_name} exceeds {max_length} characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        values[field_name] = value

    credential, _ = NsdlCredentials.objects.update_or_create(
        user=company_user,
        defaults=values,
    )
    logger.info(
        "NSDL credentials saved: company_user_id=%s requested_by=%s",
        company_user.id,
        request.user.id,
    )
    return Response({
        "user_id": company_user.id,
        "company": company_user.username,
        "credentials": _credential_response(credential),
    })


@api_view(["GET"])
def nsdl_file(request, clientcode, kind):
    if kind not in {"request", "response"}:
        raise Http404("NSDL file not found.")
    if _safe_clientcode(clientcode) != clientcode:
        raise Http404("NSDL file not found.")

    company_user = _requested_company_user(request)
    if company_user is None or not UserDetails.objects.filter(
        clientcode=clientcode,
        user=company_user,
    ).exists():
        raise Http404("NSDL file not found.")

    path = (
        Path(settings.BASE_DIR)
        / "static"
        / "nsdl_data"
        / clientcode
        / f"nsdl_{kind}.txt"
    )
    if not path.is_file():
        raise Http404("NSDL file not found.")
    return FileResponse(
        path.open("rb"),
        content_type="text/plain",
        as_attachment=True,
        filename=path.name,
    )


@api_view(["POST"])
def nsdl_ucc_modify(request, clientcode):
    clientcode = _text(clientcode)
    if not clientcode:
        return Response(
            {"success": False, "msg": "Client code is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_user = _requested_company_user(request)
    if company_user is None:
        return Response(
            {"success": False, "msg": "Company not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    client = UserDetails.objects.filter(
        clientcode=clientcode,
        user=company_user,
    ).first()
    if not client:
        return Response(
            {"success": False, "msg": "Client not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    api_not_selected = reject_if_api_not_selected(client, "NSDL")
    if api_not_selected:
        return api_not_selected
    already_pushed = reject_if_already_pushed(client, "nsdl_push", "NSDL")
    if already_pushed:
        return already_pushed
    order_blocked = reject_if_provider_order_blocked(client, "NSDL")
    if order_blocked:
        return order_blocked
    _set_nsdl_push_state(client, False)

    errors = []
    credential = _fetch_nsdl_credentials(company_user)
    nsdl_defaults = _fetch_nsdl_defaults(errors)

    environment = _text(
        request.data.get("environment")
        or getattr(settings, "NSDL_KYC_ENVIRONMENT", "uat")
    ).casefold()
    if environment not in {"uat", "live"}:
        _record_error(
            errors,
            "Unknown NSDL environment %s; using uat for payload generation",
            environment,
        )
        logger.info(
            "NSDL environment fallback applied: clientcode=%s requested=%s fallback=uat",
            clientcode,
            environment,
        )
        environment = "uat"

    logger.info(
        "NSDL request started: clientcode=%s company_user_id=%s environment=%s",
        clientcode,
        company_user.id,
        environment,
    )
    payload = None
    try:
        payload, client_id = _build_nsdl_payload(
            client,
            credential or {},
            request.data.get("client_id"),
            nsdl_defaults=nsdl_defaults,
            errors=errors,
        )
        logger.info(
            "NSDL payload generated: clientcode=%s client_id=%s error_count=%s",
            clientcode,
            bool(client_id),
            len(_unique_errors(errors)),
        )
        _save_artifact(clientcode, "request", payload)
        request_url = _artifact_url(
            request,
            clientcode,
            "request",
            company_user,
        )
        if errors:
            payload_error = errors[0]
            _set_nsdl_push_state(client, False)
            logger.error(
                "NSDL payload error for %s: %s",
                clientcode,
                payload_error,
            )
            response_url = _save_nsdl_error_response(
                request,
                clientcode,
                company_user,
                payload_error,
                "NSDL_PAYLOAD_ERROR",
            )
            error_data = _nsdl_error_data(
                payload_error,
                "NSDL_PAYLOAD_ERROR",
            )
            return Response(
                {
                    **error_data,
                    "request_payload": payload,
                    "nsdl_request_url": request_url,
                    "nsdl_response_url": response_url,
                    "nsdl_response": error_data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    except NsdlError as exc:
        _set_nsdl_push_state(client, False)
        logger.error("NSDL payload rejected for %s: %s", clientcode, exc)
        response_url = _save_nsdl_error_response(
            request,
            clientcode,
            company_user,
            exc,
            "NSDL_PAYLOAD_ERROR",
        )
        error_data = _nsdl_error_data(exc, "NSDL_PAYLOAD_ERROR")
        return Response(
            {
                **error_data,
                "nsdl_response": error_data,
                "nsdl_response_url": response_url,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except OSError as exc:
        _set_nsdl_push_state(client, False)
        logger.exception("Unable to save NSDL request for %s", clientcode)
        response_url = _save_nsdl_error_response(
            request,
            clientcode,
            company_user,
            exc,
            "NSDL_REQUEST_FILE_ERROR",
            errors,
        )
        error_data = _nsdl_error_data(exc, "NSDL_REQUEST_FILE_ERROR", errors)
        return Response(
            {
                **error_data,
                "request_payload": payload,
                "nsdl_response": error_data,
                "nsdl_response_url": response_url,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not credential:
        _set_nsdl_push_state(client, False)
        message = "NSDL credentials are not configured."
        logger.info(
            "NSDL submission skipped because credentials are missing: clientcode=%s environment=%s",
            clientcode,
            environment,
        )
        response_url = _save_nsdl_error_response(
            request,
            clientcode,
            company_user,
            message,
            "NSDL_CREDENTIAL_ERROR",
            errors,
        )
        error_data = _nsdl_error_data(message, "NSDL_CREDENTIAL_ERROR", errors)
        return Response(
            {
                **error_data,
                "request_payload": payload,
                "nsdl_response": error_data,
                "nsdl_request_url": request_url,
                "nsdl_response_url": response_url,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        response, response_data, request_reference = _submit_nsdl(
            credential,
            environment,
            payload,
        )
        response_data = _with_nsdl_errors(response_data, errors)
        _save_artifact(clientcode, "response", response_data)
        response_url = _artifact_url(
            request,
            clientcode,
            "response",
            company_user,
        )
    except NsdlError as exc:
        _set_nsdl_push_state(client, False)
        logger.error("NSDL submission failed for %s: %s", clientcode, exc)
        error_data = _nsdl_error_data(exc, "NSDL_SUBMISSION_ERROR", errors)
        response_url = ""
        try:
            _save_artifact(clientcode, "response", error_data)
            response_url = _artifact_url(
                request,
                clientcode,
                "response",
                company_user,
            )
        except OSError:
            logger.exception("Unable to save NSDL error response for %s", clientcode)
        return Response(
            {
                **error_data,
                "request_payload": payload,
                "nsdl_response": error_data,
                "nsdl_request_url": request_url,
                "nsdl_response_url": response_url,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except OSError as exc:
        _set_nsdl_push_state(client, False)
        logger.exception("Unable to save NSDL response for %s", clientcode)
        response_url = _save_nsdl_error_response(
            request,
            clientcode,
            company_user,
            exc,
            "NSDL_RESPONSE_FILE_ERROR",
            errors,
        )
        error_data = _nsdl_error_data(exc, "NSDL_RESPONSE_FILE_ERROR", errors)
        return Response(
            {
                **error_data,
                "request_payload": payload,
                "nsdl_response": error_data,
                "nsdl_request_url": request_url,
                "nsdl_response_url": response_url,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    api_error = (
        isinstance(response_data, dict)
        and _text(response_data.get("error")) not in {"", "0", "200"}
    )
    if not response.ok or api_error:
        _set_nsdl_push_state(client, False)
        message = _response_error(response_data, "NSDL request was rejected.")
        logger.error(
            "NSDL rejected request: clientcode=%s reference=%s status=%s message=%s",
            clientcode,
            request_reference,
            response.status_code,
            message,
        )
        return Response(
            {
                "success": False,
                "msg": message,
                "request_reference": request_reference,
                "request_payload": payload,
                "nsdl_request_url": request_url,
                "nsdl_response_url": response_url,
                "nsdl_response": response_data,
                "errors": _unique_errors(errors),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    nsdl_dpid = f"{credential.requesterid}{client_id}"
    client.dpid = nsdl_dpid
    client.dptype = "NSDL"
    try:
        client.save(update_fields=["dpid", "dptype", "updated_at"])
    except DatabaseError:
        _set_nsdl_push_state(client, False)
        logger.exception("NSDL succeeded but UserDetails update failed for %s", clientcode)
        return Response(
            {
                "success": False,
                "msg": "NSDL completed, but UserDetails could not be updated.",
                "request_reference": request_reference,
                "request_payload": payload,
                "nsdl_request_url": request_url,
                "nsdl_response_url": response_url,
                "nsdl_response": response_data,
                "errors": _unique_errors(errors),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    _set_nsdl_push_state(client, True)
    logger.info(
        "NSDL request completed: clientcode=%s reference=%s dpid=%s",
        clientcode,
        request_reference,
        nsdl_dpid,
    )
    return Response({
        "success": True,
        "msg": "NSDL account request completed successfully.",
        "clientcode": clientcode,
        "dpid": nsdl_dpid,
        "request_reference": request_reference,
        "submitted": True,
        "request_payload": payload,
        "nsdl_request_url": request_url,
        "nsdl_response_url": response_url,
        "nsdl_response": response_data,
        "errors": _unique_errors(errors),
    })
