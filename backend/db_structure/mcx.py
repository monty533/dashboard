"""MCX KYC integration for the Django dashboard.

The MCX reference integration was built around a workflow mapper.  This
project does not have that mapper, so this module builds the same category-01
payload directly from ``UserDetails`` and the editable ``Mcx`` defaults row.
"""

import base64
import datetime as dt
import json
import logging
import re
from collections.abc import Mapping
from urllib.parse import quote

import requests
from Crypto.Cipher import AES
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Mcx,
    McxAccountTypeMaster,
    McxCredentials,
    McxErrorCode,
    McxGenderMaster,
    McxIncomeRangeMaster,
    McxMaritalStatusMaster,
    McxOccupationMaster,
    McxStateCityMaster,
    UserDetails,
)
from .views import _requested_company_user
from .push_tracking import (
    reject_if_already_pushed,
    reject_if_api_not_selected,
    reject_if_provider_order_blocked,
)

ALLOWED_VALUES = {
    "nationality": {"1", "2"},
    "permanent_address_same_as_corresponding_address": {"Y", "N"},
    "politically_exposed_person": {"0", "1", "2"},
    "client_type_corporate": {"Y", "N"},
    "relationship_with_client_for_mobile_no": {"1", "2", "3", "4"},
    "relationship_with_client_for_email_id": {"1", "2", "3", "4"},
}

TOKEN_ENDPOINT = "token"

ADD_ENDPOINT = "add"


# MCX category-01 record shape.  Keep optional fields in the payload even
# when their value is empty; the exchange expects a fixed record layout.
MCX_RECORD_FIELDS = (
    "address_1_corresponding",
    "address_1_permanent",
    "address_2_corresponding",
    "address_2_permanent",
    "address_3_corresponding",
    "address_3_permanent",
    "address_of_contact_person_1",
    "address_of_contact_person_2",
    "address_of_contact_person_3",
    "address_of_contact_person_4",
    "address_of_contact_person_5",
    "bank_account_number_1",
    "bank_account_number_2",
    "bank_account_number_3",
    "bank_account_type_1",
    "bank_account_type_2",
    "bank_account_type_3",
    "bank_branch_address_1",
    "bank_branch_address_2",
    "bank_branch_address_3",
    "bank_name_1",
    "bank_name_2",
    "bank_name_3",
    "beneficiary_account_id_1",
    "beneficiary_account_id_2",
    "beneficiary_account_id_3",
    "category",
    "cin_lei",
    "client_agreement_date",
    "client_code",
    "client_email_id",
    "client_name",
    "client_status",
    "client_type_corporate",
    "contact_details_of_contact_person_1",
    "contact_details_of_contact_person_2",
    "contact_details_of_contact_person_3",
    "contact_details_of_contact_person_4",
    "contact_details_of_contact_person_5",
    "country_corresponding",
    "country_permanent",
    "cp_code",
    "date_of_birth_incorporation",
    "date_of_commencement_of_business",
    "date_of_registration",
    "depository_id_1",
    "depository_id_2",
    "depository_id_3",
    "depository_name_1",
    "depository_name_2",
    "depository_name_3",
    "designation_of_contact_person_1",
    "designation_of_contact_person_2",
    "designation_of_contact_person_3",
    "designation_of_contact_person_4",
    "designation_of_contact_person_5",
    "din_of_contact_person_1",
    "din_of_contact_person_2",
    "din_of_contact_person_3",
    "din_of_contact_person_4",
    "din_of_contact_person_5",
    "email_id_of_contact_person_1",
    "email_id_of_contact_person_2",
    "email_id_of_contact_person_3",
    "email_id_of_contact_person_4",
    "email_id_of_contact_person_5",
    "fathers_husbands_guardians_name",
    "flag",
    "gender",
    "in_person_verification",
    "income_as_on_date",
    "income_details_per_annum",
    "issue_date_of_proof",
    "issue_place_of_proof",
    "marital_status",
    "mobile_number",
    "name_of_contact_person_1",
    "name_of_contact_person_2",
    "name_of_contact_person_3",
    "name_of_contact_person_4",
    "name_of_contact_person_5",
    "name_of_the_authorized_contact_person_for_email_id",
    "name_of_the_authorized_contact_person_for_mobile_no",
    "nationality",
    "nationality_other",
    "networth_as_on_date",
    "networth_in_rs_usd",
    "nomination",
    "occupation",
    "occupation_details_for_others",
    "pan",
    "pan_of_contact_person_1",
    "pan_of_contact_person_2",
    "pan_of_contact_person_3",
    "pan_of_contact_person_4",
    "pan_of_contact_person_5",
    "permanent_address_same_as_corresponding_address",
    "pin_code_corresponding",
    "pin_code_permanent",
    "place_of_incorporation",
    "place_of_registration",
    "politically_exposed_person",
    "proof_number",
    "proof_type",
    "registering_authority",
    "registration_number_of_client",
    "relationship_code",
    "relationship_with_client_for_email_id",
    "relationship_with_client_for_mobile_no",
    "remarks",
    "reserved_1",
    "reserved_2",
    "reserved_3",
    "reserved_4",
    "reserved_5",
    "reserved_6",
    "state_city_code_corresponding",
    "state_city_code_permanent",
    "telephone_number_o",
    "telephone_number_r",
    "uid_number",
    "uid_of_contact_person_1",
    "uid_of_contact_person_2",
    "uid_of_contact_person_3",
    "uid_of_contact_person_4",
    "uid_of_contact_person_5",
)


logger = logging.getLogger(__name__)


def _set_mcx_push_state(client, state):
    """Store only the successful MCX time; keep mcx_push as permission."""
    if not state:
        return
    try:
        client.mcx_push_at = timezone.localtime()
        client.save(update_fields=['mcx_push_at'])
    except DatabaseError:
        logger.exception('Unable to save MCX push state: clientcode=%s', client.clientcode)

MCX_CLIENT_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}\Z")
MCX_AES_KEY_PATTERN = re.compile(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{48}|[0-9a-fA-F]{64})\Z")
MCX_DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%Y%m%d",
)


class McxRuntimeError(Exception):
    """A safe, user-facing MCX integration error."""

    def __init__(self, stage, message, details=None):
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.details = details or {}


def _mcx_error_message(code, fallback=None):
    """Read the editable provider message from the MCX error-code table."""
    code = _text(code)
    if not code:
        return fallback or "Unknown MCX error"
    try:
        message = McxErrorCode.objects.filter(code=code).values_list(
            "message", flat=True
        ).first()
        if message:
            return _text(message)
    except DatabaseError:
        logger.exception("MCX error-code lookup failed: code=%s", code)
    return fallback


def _text(value):
    return "" if value is None else str(value).strip()


def _aes_key_bytes(value):
    key_hex = _text(value)
    if not MCX_AES_KEY_PATTERN.fullmatch(key_hex):
        raise ValueError(
            "MCX AES key must be a valid 16, 24, or 32-byte hexadecimal key."
        )
    return bytes.fromhex(key_hex)


def _yes(value):
    return _text(value).casefold() in {"1", "true", "yes", "y"}


def _getter(client):
    if isinstance(client, Mapping):
        values = {str(key).lower(): value for key, value in client.items()}
    else:
        values = {
            field.name.lower(): getattr(client, field.name, "")
            for field in client._meta.concrete_fields
        }

    def get(*names):
        for name in names:
            value = values.get(str(name).lower())
            if value is not None and _text(value):
                return _text(value)
        return ""

    return get


def _parse_date(value):
    value = _text(value)
    if not value:
        return None
    candidate = value.split(" ", 1)[0]
    for date_format in MCX_DATE_FORMATS:
        try:
            return dt.datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    match = re.search(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", value)
    if match:
        for date_format in MCX_DATE_FORMATS:
            try:
                return dt.datetime.strptime(match.group(), date_format).date()
            except ValueError:
                continue
    return None


def _mcx_date(value):
    parsed = _parse_date(value)
    return parsed.strftime("%d%m%Y") if parsed else ""


def _normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _master_code(model, label_field, code_field, value):
    raw = _text(value)
    if not raw:
        return ""
    try:
        direct_code = model.objects.filter(
            **{f"{code_field}__iexact": raw}
        ).values_list(code_field, flat=True).first()
        if direct_code:
            logger.debug(
                "MCX master code found: table=%s code_field=%s",
                model._meta.db_table,
                code_field,
            )
            return _text(direct_code)
        direct = model.objects.filter(
            **{f"{label_field}__iexact": raw}
        ).values_list(code_field, flat=True).first()
        if direct:
            logger.debug(
                "MCX master value mapped: table=%s field=%s",
                model._meta.db_table,
                label_field,
            )
            return _text(direct)
        target = _normalized(raw)
        for label, code in model.objects.values_list(label_field, code_field):
            if _normalized(label) == target and _text(code):
                logger.debug(
                    "MCX normalized master value mapped: table=%s field=%s",
                    model._meta.db_table,
                    label_field,
                )
                return _text(code)
    except DatabaseError:
        logger.exception("MCX master lookup failed: table=%s", model._meta.db_table)
    logger.warning(
        "MCX master value not mapped: table=%s field=%s",
        model._meta.db_table,
        label_field,
    )
    return ""


def _gender_code(value):
    raw = _text(value)
    code = _master_code(McxGenderMaster, "gender", "gender_code", raw)
    if code:
        return code

def _country_code(value):
    raw = _text(value)
    if raw.isdigit():
        return raw
    return {"india": "85"}.get(raw.casefold(), raw)


def _marital_code(value):
    raw = _text(value)
    return _master_code(McxMaritalStatusMaster, "marital_status", "marital_code", raw)


def _income_code(value):
    raw = _text(value)
    return _master_code(McxIncomeRangeMaster, "income_range", "income_code", raw)


def _occupation_code(value):
    raw = _text(value)
    return _master_code(McxOccupationMaster, "occupation_name", "occupation_code", raw)


def _account_type_code(value):
    raw = _text(value)
    return _master_code(McxAccountTypeMaster, "account_type", "account_code", raw)


def _address_lines(get):
    address = get("aadhaar_address") or " ".join(
        value for value in (
            get("addressline1"),
            get("addressline2"),
            get("addressline3"),
        ) if value
    )
    address = re.sub(r"\s+", " ", address).strip()
    return [address[index:index + 255] for index in range(0, len(address), 255)][:3]


def _state_city_code(state, city):
    state = _text(state)
    city = _text(city)
    try:
        row = McxStateCityMaster.objects.filter(
            state__iexact=state,
            city__iexact=city,
        ).values_list("state_city_code", flat=True).first()
        if row:
            return _text(row)
        normalized_state = _normalized(state)
        normalized_city = _normalized(city)
        for row_state, row_city, code in McxStateCityMaster.objects.values_list(
            "state", "city", "state_city_code"
        ):
            if _normalized(row_state) == normalized_state and _normalized(row_city) == normalized_city:
                return _text(code)
    except DatabaseError:
        logger.exception("MCX state-city lookup failed: state=%s city=%s", state, city)
    logger.warning("MCX state-city mapping not found: state=%s city=%s", state, city)
    return ""


def _defaults(mcx_master):
    return {
        field.name: _text(getattr(mcx_master, field.name, ""))
        for field in Mcx._meta.concrete_fields
        if not field.primary_key
    }


def _build_record(client, mcx_master):
    get = _getter(client)
    logger.debug("MCX master loaded: master_id=%s", mcx_master.id)
    defaults = _defaults(mcx_master)
    logger.debug("MCX defaults loaded: field_count=%s", len(defaults))
    address_lines = _address_lines(get)
    address_1 = address_lines[0] if address_lines else ""
    address_2 = address_lines[1] if len(address_lines) > 1 else ""
    address_3 = address_lines[2] if len(address_lines) > 2 else ""
    state = get("aadhaar_state")
    city = get("aadhaar_dist")
    state_city_code = _state_city_code(state, city)
    bank_address = get("bankaddress") or get("branchname")
    income = _income_code(get("annual_income"))
    occupation = _occupation_code(get("occupation"))
    name = get("aadhaar_name", "name") or get("clientcode")
    record = {
        field: defaults.get(field, "")
        for field in MCX_RECORD_FIELDS
    }
    record.update({
        "client_code": get("clientcode"),
        "client_name": name,
        "pan": get("pan").upper(),
        "gender": _gender_code(get("aadhaar_gender", "gender")),
        "fathers_husbands_guardians_name": get("fathername", "aadhaar_fathername"),
        "marital_status": _marital_code(get("marital_status")),
        "nationality": defaults.get("nationality") or "1",
        "client_email_id": get("email"),
        "address_1_corresponding": address_1,
        "address_2_corresponding": address_2,
        "address_3_corresponding": address_3,
        "country_corresponding": _country_code(get("aadhaar_country")),
        "state_city_code_corresponding": state_city_code,
        "pin_code_corresponding": get("aadhaar_pincode"),
        "mobile_number": get("mobile"),
        "date_of_birth_incorporation": _mcx_date(get("aadhaar_dob")),
        "bank_name_1": get("bankname"),
        "bank_branch_address_1": bank_address,
        "bank_account_number_1": get("bankaccountnumber"),
        "bank_account_type_1": _account_type_code(get("accounttype")),
        "occupation": occupation,
        "income_details_per_annum": income,
        "income_as_on_date": _mcx_date(get("annual_income_date")) if income else "",
        "networth_in_rs_usd": get("networth"),
        "networth_as_on_date": _mcx_date(get("networth_date")) if get("networth") else "",
    })
    if _text(defaults.get("permanent_address_same_as_corresponding_address", "Y")) == "N":
        record.update({
            "address_1_permanent": address_1,
            "address_2_permanent": address_2,
            "address_3_permanent": address_3,
            "country_permanent": _country_code(get("aadhaar_country")),
            "state_city_code_permanent": state_city_code,
            "pin_code_permanent": get("aadhaar_pincode"),
        })
    logger.debug(
        "MCX record built: clientcode=%s gender_present=%s marital_present=%s "
        "occupation_present=%s income_present=%s state_city_present=%s",
        record.get("client_code"),
        bool(record.get("gender")),
        bool(record.get("marital_status")),
        bool(record.get("occupation")),
        bool(record.get("income_details_per_annum")),
        bool(record.get("state_city_code_corresponding")),
    )
    return record


def _build_payload(client, mcx_master, credentials):
    records = [_build_record(client, mcx_master)]
    now = timezone.localtime()
    member_id = _text(
        credentials.get("member_id", "")
        if isinstance(credentials, Mapping)
        else getattr(credentials, "member_id", "")
    )
    payload = {
        "record_type": _text(getattr(mcx_master, "record_type")),
        "member_type": _text(getattr(mcx_master, "member_type")),
        "tmid": int(member_id) if member_id.isdigit() else member_id,
        "date": timezone.localdate().strftime("%d%m%Y"),
        "batch_number": now.strftime("%d%m%Y%H%M%S"),
        "record_count": str(len(records)),
        "records": records,
    }
    logger.info(
        "MCX payload built: clientcode=%s tmid=%s record_count=%s",
        records[0].get("client_code"),
        payload["tmid"],
        payload["record_count"],
    )
    return payload


def _validate_payload(payload):
    if not isinstance(payload.get("records"), list) or not payload["records"]:
        logger.warning("MCX payload validation failed: records are missing")
        raise McxRuntimeError("payload", "At least one MCX record is required")
    errors = []
    if not str(payload.get("tmid", "")).isdigit():
        errors.append("tmid must be numeric; update the MCX Member ID in credentials")
    for index, record in enumerate(payload["records"]):
        prefix = f"records[{index}]"
        for field, values in ALLOWED_VALUES.items():
            value = _text(record.get(field))
            allowed_values = {values} if isinstance(values, str) else values
            if value and value not in allowed_values:
                errors.append(f"{prefix}: invalid {field}={value}")
        if not _text(record.get("income_details_per_annum")) and not _text(record.get("networth_in_rs_usd")):
            errors.append(f"{prefix}: income_details_per_annum or networth_in_rs_usd is required")
    if errors:
        logger.warning(
            "MCX payload validation failed: tmid=%s error_count=%s",
            payload.get("tmid"),
            len(errors),
        )
        raise McxRuntimeError(
            "validation",
            f"MCX payload validation failed: {'; '.join(errors)}",
            {"errors": errors},
        )


def _base_url(environment):
    if environment == "live":
        return _text(getattr(settings, "MCX_KYC_LIVE_BASE_URL", ""))
    return _text(getattr(settings, "MCX_KYC_UAT_BASE_URL", ""))


def _credentials(company):
    credential = McxCredentials.objects.filter(user=company).first()
    logger.debug(
        "MCX credentials lookup: company_user_id=%s configured=%s",
        company.id,
        bool(credential),
    )
    if credential is None:
        raise McxRuntimeError("credentials", "MCX credentials are not configured.")
    missing = [field for field in ("member_id", "api_key", "aes_key") if not _text(getattr(credential, field, ""))]
    if missing:
        raise McxRuntimeError("credentials", f"MCX credentials missing: {', '.join(missing)}")
    try:
        _aes_key_bytes(credential.aes_key)
    except ValueError as exc:
        raise McxRuntimeError("credentials", str(exc)) from exc
    environment = _text(credential.environment).lower() or "uat"
    base_url = _base_url(environment)
    if not base_url:
        setting_name = (
            "MCX_KYC_LIVE_BASE_URL"
            if environment == "live"
            else "MCX_KYC_UAT_BASE_URL"
        )
        raise McxRuntimeError(
            "credentials",
            f"MCX base URL is not configured for {environment}. "
            f"Set {setting_name} in backend/.env.",
        )
    logger.info(
        "MCX credentials ready: company_user_id=%s environment=%s",
        company.id,
        environment,
    )
    return credential, base_url


def _encrypt_payload(payload, aes_key_hex):
    key = _aes_key_bytes(aes_key_hex)
    nonce = __import__("os").urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(json.dumps(payload, separators=(",", ":")).encode())
    return base64.b64encode(nonce + ciphertext + tag).decode("ascii")


def _decrypt_response(body, aes_key_hex):
    raw = base64.b64decode(body)
    nonce, ciphertext, tag = raw[:12], raw[12:-16], raw[-16:]
    cipher = AES.new(_aes_key_bytes(aes_key_hex), AES.MODE_GCM, nonce=nonce)
    return json.loads(cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8"))


def _response_body(response, credential, endpoint):
    content_type = _text(response.headers.get("Content-Type")).lower()
    logger.debug(
        "MCX response received: endpoint=%s status_code=%s content_type=%s",
        endpoint,
        response.status_code,
        content_type or "unknown",
    )
    if "application/base64" in content_type:
        try:
            return _decrypt_response(response.text, credential.aes_key)
        except Exception as exc:
            raise McxRuntimeError(endpoint, f"Could not decrypt MCX {endpoint} response.", {"exception": str(exc)}) from exc
    try:
        return response.json()
    except ValueError:
        return {"raw_response": response.text, "status_code": response.status_code}


def _request_mcx(credential, base_url, payload):
    token_url = f"{base_url.rstrip('/')}/{TOKEN_ENDPOINT}"
    logger.info(
        "MCX token request started: endpoint=%s member_id=%s",
        token_url,
        credential.member_id,
    )
    try:
        token_response = requests.post(
            token_url,
            headers={"User-Agent": "JM-Dashboard", "tm-id": credential.member_id, "api-key": credential.api_key},
            timeout=getattr(settings, "MCX_KYC_TIMEOUT", 30),
            verify=getattr(settings, "MCX_KYC_VERIFY_SSL", True),
        )
    except requests.RequestException as exc:
        raise McxRuntimeError("token", "MCX token request failed.", {"exception": str(exc)}) from exc
    if token_response.status_code >= 400:
        logger.warning("MCX token request failed: status_code=%s", token_response.status_code)
        raise McxRuntimeError("token", f"MCX token request returned HTTP {token_response.status_code}.", {"response": token_response.text})
    token_data = _response_body(token_response, credential, TOKEN_ENDPOINT)
    token = token_data.get("token") if isinstance(token_data, dict) else ""
    if not token:
        logger.warning("MCX token response did not contain an access token")
        raise McxRuntimeError("token", "MCX did not return an access token.", {"response": token_data})
    encrypted = _encrypt_payload(payload, credential.aes_key)
    add_url = f"{base_url.rstrip('/')}/{ADD_ENDPOINT}"
    logger.info(
        "MCX add request started: endpoint=%s record_count=%s",
        add_url,
        len(payload.get("records", [])),
    )
    try:
        add_response = requests.post(
            add_url,
            headers={"User-Agent": "JM-Dashboard", "Authorization": f"Bearer {token}", "Content-Type": "application/base64"},
            data=encrypted,
            timeout=getattr(settings, "MCX_KYC_TIMEOUT", 30),
            verify=getattr(settings, "MCX_KYC_VERIFY_SSL", True),
        )
    except requests.RequestException as exc:
        raise McxRuntimeError("add", "MCX add request failed.", {"exception": str(exc)}) from exc
    body = _response_body(add_response, credential, ADD_ENDPOINT)
    if add_response.status_code >= 400:
        logger.warning("MCX add request failed: status_code=%s", add_response.status_code)
        raise McxRuntimeError("add", f"MCX add request returned HTTP {add_response.status_code}.", {"response": body})
    logger.info("MCX add request completed: status_code=%s", add_response.status_code)
    return body


def _safe_clientcode(clientcode):
    return clientcode if MCX_CLIENT_CODE_PATTERN.fullmatch(clientcode) else ""


def _save_artifact(clientcode, filename, value):
    directory = settings.BASE_DIR / "static" / "mcx_data" / _safe_clientcode(clientcode)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    temporary = path.with_name(f".{path.name}.tmp")
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
    logger.info(
        "MCX artifact saved: clientcode=%s filename=%s bytes=%s",
        clientcode,
        filename,
        len(value.encode("utf-8")),
    )
    return path


def _artifact_url(request, clientcode, kind):
    return request.build_absolute_uri(f"/api/mcx_file/{quote(clientcode, safe='')}/{kind}/")


@api_view(["GET"])
def mcx_file(request, clientcode, kind):
    logger.info("MCX artifact download requested: clientcode=%s kind=%s", clientcode, kind)
    if kind not in {"request", "response"}:
        return Response({"error": "Unsupported MCX file."}, status=status.HTTP_404_NOT_FOUND)
    company = _requested_company_user(request)
    if company is None:
        return Response({"error": "Company not found."}, status=status.HTTP_404_NOT_FOUND)
    if not (request.user.is_staff or request.user.is_superuser):
        if not UserDetails.objects.filter(clientcode=clientcode, user=request.user).exists():
            return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
    path = settings.BASE_DIR / "static" / "mcx_data" / _safe_clientcode(clientcode) / f"mcx_{kind}.txt"
    if not path.is_file():
        return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
    from django.http import FileResponse
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="text/plain")


@api_view(["GET", "POST"])
def mcx_credentials_view(request):
    company = _requested_company_user(request)
    if company is None:
        return Response({"error": "Company not found."}, status=status.HTTP_404_NOT_FOUND)
    credential = McxCredentials.objects.filter(user=company).first()
    if request.method == "GET":
        return Response({
            "user_id": company.id,
            "company": company.username,
            "credentials": {
                "environment": credential.environment if credential else "uat",
                "member_id": credential.member_id if credential else "",
                "api_key": credential.api_key if credential else "",
                "aes_key": credential.aes_key if credential else "",
            },
        })
    values = {
        field: _text(request.data.get(field, ""))
        for field in ("environment", "member_id", "api_key", "aes_key")
    }
    values["environment"] = values["environment"].lower() or "uat"
    if values["environment"] not in {"uat", "live"}:
        return Response({"error": "Environment must be uat or live."}, status=400)
    if values["aes_key"]:
        try:
            _aes_key_bytes(values["aes_key"])
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
    if credential:
        if not values["api_key"]:
            values.pop("api_key")
        if not values["aes_key"]:
            values.pop("aes_key")
    credential, _ = McxCredentials.objects.update_or_create(user=company, defaults=values)
    logger.info("MCX credentials saved: company_user_id=%s environment=%s", company.id, credential.environment)
    return Response({
        "success": True,
        "user_id": company.id,
        "company": company.username,
        "credentials": {
            "environment": credential.environment,
            "member_id": credential.member_id,
            "api_key": credential.api_key,
            "aes_key": credential.aes_key,
        },
    })


@api_view(["POST"])
def mcx_ucc_modify(request, clientcode):
    logger.info("MCX UCC request started: clientcode=%s", clientcode)
    if not MCX_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({"success": False, "message": "Invalid client code."}, status=400)
    company = _requested_company_user(request)
    if company is None:
        return Response({"success": False, "message": "Company not found."}, status=404)
    client = UserDetails.objects.filter(clientcode=clientcode, user=company).first()
    if client is None:
        return Response({"success": False, "message": "Client not found."}, status=404)
    api_not_selected = reject_if_api_not_selected(client, "MCX")
    if api_not_selected:
        return api_not_selected
    already_pushed = reject_if_already_pushed(client, "mcx_push", "MCX")
    if already_pushed:
        return already_pushed
    order_blocked = reject_if_provider_order_blocked(client, "MCX")
    if order_blocked:
        return order_blocked
    _set_mcx_push_state(client, False)
    mcx_master = Mcx.objects.order_by("id").first()
    if mcx_master is None:
        _set_mcx_push_state(client, False)
        return Response({"success": False, "message": "MCX master record not found."}, status=400)
    credential = None
    payload = None
    request_url = ""
    try:
        credential_row = McxCredentials.objects.filter(user=company).first()
        payload = _build_payload(client, mcx_master, credential_row or {})
        _save_artifact(clientcode, "mcx_request.txt", payload)
        request_url = _artifact_url(request, clientcode, "request")
        credential, base_url = _credentials(company)
        _validate_payload(payload)
        if request.query_params.get("preview") == "1" or not getattr(settings, "MCX_KYC_SUBMIT", False):
            logger.info(
                "MCX payload preview returned: clientcode=%s submit_enabled=%s",
                clientcode,
                bool(getattr(settings, "MCX_KYC_SUBMIT", False)),
            )
            return Response({
                "success": True,
                "preview": True,
                "message": "MCX payload generated. Provider submission is disabled.",
                "mcx_request_url": request_url,
                "payload": payload,
            }, status=200)
        response = _request_mcx(credential, base_url, payload)
        _save_artifact(clientcode, "mcx_response.txt", response)
        errors = []
        for row in (response.get("results", []) if isinstance(response, dict) else []):
            if not isinstance(row, dict):
                continue
            code = _text(row.get("error_codes"))
            if code or _text(row.get("status")).upper() == "FAIL":
                errors.append({
                    "client_code": row.get("client_code"),
                    "code": code,
                    "message": row.get("error_description") or _mcx_error_message(code),
                })
        logger.info(
            "MCX UCC request completed: clientcode=%s error_count=%s",
            clientcode,
            len(errors),
        )
        _set_mcx_push_state(client, not errors)
        return Response({
            "success": not errors,
            "message": "MCX add-UCC request accepted." if not errors else "MCX rejected the add-UCC request.",
            "mcx_request_url": request_url,
            "mcx_response_url": _artifact_url(request, clientcode, "response"),
            "mcx_response": response,
            "errors": errors,
        }, status=200 if not errors else 400)
    except McxRuntimeError as exc:
        _set_mcx_push_state(client, False)
        error_response = {
            "success": False,
            "stage": exc.stage,
            "error": exc.message,
            "message": exc.message,
            "msg": exc.message,
            "errors": exc.details.get("errors") if isinstance(exc.details.get("errors"), list) else [exc.message],
            "details": exc.details,
        }
        try:
            _save_artifact(clientcode, "mcx_response.txt", error_response)
        except Exception:
            logger.exception(
                "Could not save MCX error response: clientcode=%s stage=%s",
                clientcode,
                exc.stage,
            )
        logger.warning("MCX request failed: clientcode=%s stage=%s message=%s", clientcode, exc.stage, exc.message)
        return Response(
            {
                **error_response,
                "request_payload": payload,
                "mcx_request_url": request_url,
                "mcx_response": error_response,
                "mcx_response_url": _artifact_url(request, clientcode, "response"),
            },
            status=400,
        )
    except Exception as exc:
        _set_mcx_push_state(client, False)
        error_response = {
            "success": False,
            "stage": "internal",
            "error": str(exc),
            "message": str(exc),
            "msg": str(exc),
            "errors": [str(exc)],
            "details": {"exception": str(exc)},
        }
        try:
            _save_artifact(clientcode, "mcx_response.txt", error_response)
        except Exception:
            logger.exception("Could not save unexpected MCX error response: clientcode=%s", clientcode)
        logger.exception("Unexpected MCX integration failure: clientcode=%s", clientcode)
        return Response(
            {
                **error_response,
                "request_payload": payload,
                "mcx_request_url": request_url,
                "mcx_response": error_response,
                "mcx_response_url": _artifact_url(request, clientcode, "response"),
            },
            status=500,
        )
