import datetime as dt
import json
import logging
import re
from collections.abc import Mapping
from urllib.parse import quote

import requests
from django.conf import settings
from django.db import DatabaseError
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
	Nse,
	NseCredentials,
	NseIncomeRangeMaster,
	NseMaritalStatusMaster,
	NseOccupationMaster,
	NseStateCodeMaster,
	UserDetails,
)
from .views import _requested_company_user
from .push_tracking import (
    reject_if_api_not_selected,
    reject_if_already_pushed,
    reject_if_provider_order_blocked,
)

logger = logging.getLogger(__name__)

NSE_HOST = "https://api.nseindia.com"
NSE_AUTH_URL = f"{NSE_HOST}/uciservice/api/auth"
NSE_CLIENT_UPLOAD_URL = f"{NSE_HOST}/uciservice/api/clientupload"
NSE_CLIENT_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}\Z")
IFSC_URL = "https://ifsc.razorpay.com/{ifsc}"
NSE_AUTH_TIMEOUT = 10
NSE_UPLOAD_TIMEOUT = 30

NSE_DATE_FORMATS = (
	"%d-%m-%Y",
	"%d/%m/%Y",
	"%Y-%m-%d",
	"%Y/%m/%d",
	"%m/%d/%Y",
)

NSE_MASTER_FIELDS = (
	"ccdCategory",
	"ccdAddCountry",
	"ccdIpv",
	"ccdNationality",
	"ccdPermAddCountry",
	"ccdPep",
	"ccdClntTyp",
	"ccdPoaFunds",
	"ccdPriSecDp",
	"ccdAcctType",
	"ccdOptForUpi",
	"ccdSegInd",
)

NSE_MODEL_COLUMNS = frozenset(
	field.db_column
	for field in Nse._meta.concrete_fields
	if not field.primary_key
)

def _text(value):
	return '' if value is None else str(value).strip()

def _clean(value, max_length=None):
	value = _text(value)
	value = re.sub(r"[^a-zA-Z0-9,\- \n.]", "", value)
	value = re.sub(r"\s+", " ", value).strip()
	if max_length:
		return value[:max_length]
	return value


def _min_words(value):
	value = _clean(value)
	if not value:
		return ""
	parts = value.split()
	while len(parts) < 3:
		parts.append(".")
	return " ".join(parts)

def _normalize_state_name(value):
	return " ".join(_text(value).lower().casefold().split())

def _normalize_occupation_name(value):
	return " ".join(_text(value).lower().casefold().split())

def _normalize_marital_status(value):
	return " ".join(_text(value).lower().casefold().split())

def _normalize_master_label(value):
	"""Normalize harmless punctuation and whitespace differences in masters."""
	return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()

def _load_master_codes(model, label_field, code_field, normalizer):
	"""Load a small master table once instead of querying it per payload field."""
	codes = {}
	try:
		rows = model.objects.values_list(label_field, code_field)
		for label, code in rows:
			label = _text(label)
			code = _text(code)
			if label and code:
				codes[normalizer(label)] = code
				codes[_normalize_master_label(label)] = code
	except DatabaseError:
		logger.exception("Unable to load %s code master", model._meta.db_table)
	logger.debug(
		"Loaded NSE master codes: table=%s entries=%s",
		model._meta.db_table,
		len(codes),
	)
	return codes


def _master_code(model, label_field, code_field, value, normalizer, default, codes=None):
	"""Return a code from a master table, with normalized alias support."""
	raw_value = _text(value)
	if not raw_value:
		return default
	if codes is not None:
		code = codes.get(normalizer(raw_value)) or codes.get(_normalize_master_label(raw_value))
		if code:
			return code
		logger.warning(
			"NSE master lookup did not find a code: table=%s; using default",
			model._meta.db_table,
		)
		return default

	try:
		# Most values match directly, so avoid loading the full master table.
		code = model.objects.filter(
			**{f"{label_field}__iexact": raw_value}
		).values_list(code_field, flat=True).first()
		if _text(code):
			return _text(code, default)

		normalized_value = normalizer(raw_value)
		if not normalized_value:
			return default

		# Handles aliases stored in the master, such as '&' versus 'and'.
		for master_value, master_code in model.objects.values_list(label_field, code_field):
			if normalizer(master_value) == normalized_value and _text(master_code):
				return _text(master_code, default)
	except DatabaseError:
		logger.exception("Unable to fetch %s code from master", model._meta.db_table)

	logger.warning(
		"NSE master lookup did not find a code: table=%s; using default",
		model._meta.db_table,
	)
	return default


def _state_code(value, state_codes=None):
	return _master_code(
		NseStateCodeMaster,
		"state_name",
		"state_code",
		value,
		_normalize_state_name,
		"",
		codes=state_codes,
	)

def _parse_date(value):
	value = _text(value)
	match = re.search(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", value)
	candidate = match.group() if match else value.split(" ", 1)[0]
	for fmt in NSE_DATE_FORMATS:
		try:
			return dt.datetime.strptime(candidate, fmt).date()
		except ValueError:
			continue
	return None


def _format_date(value, fallback_today=False):
	parsed = _parse_date(value)
	if parsed is None and fallback_today:
		parsed = timezone.localdate()
	return parsed.strftime("%d-%m-%Y") if parsed else ""


def _split_address(*parts):
	address = _clean(" ".join(_text(part) for part in parts), 165)
	lines = ["", "", ""]
	for index in range(3):
		if not address:
			break
		if len(address) <= 55:
			lines[index] = address
			break
		split_at = address[:55].rsplit(" ", 1)[0]
		if not split_at:
			split_at = address[:55]
		lines[index] = split_at
		address = address[len(split_at):].strip()
	return [_min_words(line) for line in lines]


def _fetch_client(clientcode, company_user):
	return UserDetails.objects.filter(
		clientcode=clientcode,
		user=company_user,
	).first()


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
			field_name = name.lower()
			if field_name in values:
				return _text(values[field_name])

	return get


def _annual_income_code(value, income_codes):
	value = _text(value)
	return _master_code(
		NseIncomeRangeMaster,
		"income_range",
		"income_code",
		value,
		_normalize_income_range,
		"",
		codes=income_codes,
	)

def _marital_status_code(value, marital_status_codes):
	value = _text(value)
	return _master_code(
		NseMaritalStatusMaster,
		"marital_status",
		"marital_code",
		value,
		_normalize_marital_status,
		"",
		codes=marital_status_codes,
	)

def _occupation_code(value, occupation_codes):
	value = _text(value)
	return _master_code(
		NseOccupationMaster,
		"occupation_name",
		"occupation_code",
		value,
		_normalize_occupation_name,
		"",
		codes=occupation_codes,
	)

def _nse_row(values):
	"""Keep only columns understood by the configured NSE model."""
	return {
		key: _text(value)
		for key, value in values.items()
		if key in NSE_MODEL_COLUMNS
	}

def _normalize_income_range(value):
	value = _text(value).lower()
	value = value.replace("rs.", "").replace("rs", "")
	value = value.replace("lakhs", "lakh").replace("lacs", "lakh").replace("lac", "lakh")
	value = re.sub(r"\bcr\b", "crore", value).replace("crores", "crore")
	value = re.sub(r"[^a-z0-9]+", " ", value)
	value = " ".join(value.split())
	numbers = re.findall(r"\d+(?:\.\d+)?", value)

	if any(word in value for word in ("below", "under", "less")) and "1" in value:
		return "below 1 lakh"
	if numbers[:2] == ["1", "5"]:
		return "1 5 lakh"
	if numbers[:2] == ["5", "10"]:
		return "5 10 lakh"
	if numbers[:2] == ["10", "25"]:
		return "10 25 lakh"
	if numbers[:2] in (["25", "50"], ["50", "1"]) or (
		numbers[:2] == ["25", "1"] and "crore" in value
	):
		return "25 100 lakh"
	if any(word in value for word in ("above", "more")) and numbers[:1] == ["1"] and ("crore" in value or "cr" in value):
		return "above 1 crore"
	return value


def _safe_clientcode(clientcode):
	clientcode = _text(clientcode)
	return clientcode if NSE_CLIENT_CODE_PATTERN.fullmatch(clientcode) else ""


def _save_nse_file(clientcode, filename, data):
	client_dir = settings.BASE_DIR / "static" / "nse_data" / _safe_clientcode(clientcode)
	client_dir.mkdir(parents=True, exist_ok=True)
	path = client_dir / filename
	content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
	# Replace the previous per-client payload instead of appending to it.
	temporary_path = path.with_name(f".{path.name}.tmp")
	temporary_path.write_text(content, encoding="utf-8")
	temporary_path.replace(path)
	logger.debug(
		"NSE artifact saved: clientcode=%s filename=%s bytes=%s",
		clientcode,
		filename,
		len(content.encode("utf-8")),
	)
	return path


def _save_nse_error_response(request, clientcode, message, response_data=None):
	"""Save a JSON response artifact for local or NSE-provider errors."""
	error_message = _text(message)
	error_body = dict(response_data) if isinstance(response_data, dict) else {
		"success": False,
		"error": error_message,
		"msg": error_message,
	}
	error_body.setdefault("success", False)
	error_body.setdefault("error", error_message)
	error_body.setdefault("msg", error_message)
	error_body.setdefault("errors", [error_message])
	try:
		_save_nse_file(
			clientcode,
			"nse_response.txt",
			error_body,
		)
		logger.info("NSE error response saved: clientcode=%s", clientcode)
		return _nse_file_url(request, clientcode, "nse_response.txt")
	except (OSError, ValueError):
		logger.exception("Unable to save NSE error response: clientcode=%s", clientcode)
		return ""


def _nse_file_url(request, clientcode, filename):
	kind = {
		"nse_request.txt": "request",
		"nse_response.txt": "response",
	}.get(filename)
	if kind is None:
		raise ValueError("Unsupported NSE file name")
	client_part = quote(_safe_clientcode(clientcode), safe="")
	return request.build_absolute_uri(f"/api/nse_file/{client_part}/{kind}/")


@api_view(["GET"])
def nse_file(request, clientcode, kind):
	"""Serve one client's NSE artifacts only to its owner or an administrator."""
	clients = UserDetails.objects.filter(clientcode=clientcode)
	if not (request.user.is_staff or request.user.is_superuser):
		clients = clients.filter(user=request.user)
	if not clients.exists():
		logger.warning(
			"Rejected unauthorized NSE artifact request: clientcode=%s user_id=%s",
			clientcode,
			getattr(request.user, "id", None),
		)
		raise Http404("NSE file not found.")

	filename = f"nse_{kind}.txt"
	path = settings.BASE_DIR / "static" / "nse_data" / clientcode / filename
	if not path.is_file():
		logger.warning("NSE artifact missing: clientcode=%s filename=%s", clientcode, filename)
		raise Http404("NSE file not found.")
	return FileResponse(
		path.open("rb"),
		as_attachment=True,
		filename=filename,
		content_type="text/plain",
	)


def _build_nse_payload(client, credential_username):
	get = _getter(client)
	clientcode = get("clientcode").upper().rsplit("-", 1)[0]
	logger.info("Building NSE payload: clientcode=%s", clientcode)
	nse_object = Nse.objects.only(*NSE_MASTER_FIELDS).order_by("id").first()
	
	if not nse_object:
		logger.error("NSE master record is missing: clientcode=%s", clientcode)
		return None, "NSE table record not found."
	logger.info("NSE master record loaded: clientcode=%s", clientcode)

	name = get("aadhaar_name")
	father_name = get("fathername")
	mobile = get("mobile")
	email = get("email")
	dob = _format_date(get("aadhaar_dob"), fallback_today=False)
	gender = get("aadhaar_gender")[:1].upper()

	address1, address2, address3 = _split_address(get("addressline1"),get("addressline2"),get("addressline3"))
	cor_address_1, cor_address_2, cor_address_3 = address1, address2, address3
	city = get("aadhaar_city")
	state = get("aadhaar_state")
	pincode = get("aadhaar_pincode")
	corr_city = city
	corr_state = state
	corr_pincode = pincode

	dpid = get("dpid").upper()
	dptype = get("dptype").upper()
	depos_id = dpid[:8] if dptype == "NSDL" else dpid[8:]
	ben_account = dpid[8:] if dptype == "CDSL" else dpid[:8]

	networth = get("networth")
	networth_date = _format_date(get("networth_date"))
	state_codes = _load_master_codes(
		NseStateCodeMaster, "state_name", "state_code", _normalize_state_name,
	)
	income_codes = _load_master_codes(
		NseIncomeRangeMaster, "income_range", "income_code", _normalize_income_range,
	)
	occupation_codes = _load_master_codes(
		NseOccupationMaster,
		"occupation_name",
		"occupation_code",
		_normalize_occupation_name,
	)
	marital_status_codes = _load_master_codes(
		NseMaritalStatusMaster,
		"marital_status",
		"marital_code",
		_normalize_marital_status,
	)
	logger.debug("NSE marital-status master loaded: entries=%s", len(marital_status_codes))
	marital_status = _marital_status_code(get("marital_status"), marital_status_codes)
	annual_income = _annual_income_code(get("annual_income"), income_codes)
	annual_income_date = _format_date(get("annual_income_date"), fallback_today=True)

	occupation = get("occupation")
	occupation_code = _occupation_code(occupation, occupation_codes)
	
	logger.debug(
		"NSE occupation resolved: clientcode=%s occupation_code=%s",
		clientcode,
		occupation_code,
	)
	
	is_dp_poa = get("isdppoa")
	nominee_enabled = _text(get("nominee_check")).casefold() == "yes"
	nominee_flag = _text(nse_object.ccdNomFlag) if nominee_enabled else "1"
	logger.info(
		"NSE nominee option resolved: clientcode=%s enabled=%s",
		clientcode,
		nominee_enabled,
	)

	state = _state_code(state, state_codes=state_codes)
	corr_state = state
	ifsc = get("ifsc")
	accountnumber = get("accountnumber")
	bankname = get("bankname")
	bankaddress = get("bankaddress")
	request_items = [_nse_row({
		"ccdMemCd": _text(credential_username),
		"ccdCd": clientcode,
		"ccdName": name,
		"ccdCategory": _text(nse_object.ccdCategory),
		"ccdPinCode": corr_pincode,
		"ccdTelNo": "",
		"ccdTvFlag": "",
		"ccdAgrDt": "",
		"ccdPanNo": get("pan"),
		"ccdRegNo": "",
		"ccdRegAuth": "",
		"ccdPlcReg": "",
		"ccdDtReg": "",
		"ccdSegInd": _text(nse_object.ccdSegInd),
		"ccdDob": dob,
		"ccdBankBrAdd": _clean(bankaddress, 150),
		"ccdDeposId": depos_id,
		"ccdAddLine1": cor_address_1,
		"ccdAddLine2": cor_address_2,
		"ccdAddLine3": cor_address_3,
		"ccdAddCity": corr_city,
		"ccdAddState": corr_state,
		"ccdAddCountry": _text(nse_object.ccdAddCountry),
		"ccdTelIsd": "",
		"ccdTelStd": "",
		"ccdMobile": mobile,
		"ccdEmail": email,
		"ccdProofType": "",
		"ccdProofNo": "",
		"ccdIssPlcProof": "",
		"ccdIssDtProof": "",
		"ccdDir1Name": "",
		"ccdDir2Name": "",
		"ccdDir3Name": "",
		"ccdDir1Desig": "",
		"ccdDir2Desig": "",
		"ccdDir3Desig": "",
		"ccdDir1Pan": "",
		"ccdDir2Pan": "",
		"ccdDir3Pan": "",
		"ccdDir1Add": "",
		"ccdDir2Add": "",
		"ccdDir3Add": "",
		"ccdDir1TelNo": "",
		"ccdDir2TelNo": "",
		"ccdDir3TelNo": "",
		"ccdDir1Email": "",
		"ccdDir2Email": "",
		"ccdDir3Email": "",
		"ccdIpv": _text(nse_object.ccdIpv),
		"ccdUccCd": "",
		"ccdRelationship": "",
		"ccdFacilityType": "",
		"ccdCin": "",
		"ccdCltStatus": _text(nse_object.ccdCltStatus),
		"ccdCltStatusReason": "",
		"ccdGender": gender,
		"ccdGuardianName": father_name,
		"ccdMaritlStatus": marital_status,
		"ccdNationality": _text(nse_object.ccdNationality),
		"ccdPermantAddFlg": _text(nse_object.ccdPermantAddFlg),
		"ccdPermAddLine1": address1,
		"ccdPermAddLine2": address2,
		"ccdPermAddLine3": address3,
		"ccdPermAddCity": city,
		"ccdPermAddState": state,
		"ccdPermAddCountry": _text(nse_object.ccdPermAddCountry),
		"ccdPermPin": pincode,
		"ccdOffcIsd": "",
		"ccdOffcStd": "",
		"ccdTelOffice": "",
		"ccdUid": "",
		"ccdDeposName": dptype,
		"ccdBenAcctNo": ben_account,
		"ccdDeposName2": "",
		"ccdDeposId2": "",
		"ccdBenAcctNo2": "",
		"ccdDeposName3": "",
		"ccdDeposId3": "",
		"ccdBenAcctNo3": "",
		"ccdGrosAnnlRnge": annual_income,
		"ccdGrosAnnlAsdate": annual_income_date,
		"ccdNetWorth": networth,
		"ccdNetWorthAsdate": networth_date,
		"ccdPep": _text(nse_object.ccdPep),
		"ccdPoi": "",
		"ccdOccupation": occupation_code,
		"ccdOccupationDtls": _text(occupation),
		"ccdBusComDt": "",
		"ccdCpCd": "",
		"ccdClntTyp": _text(nse_object.ccdClntTyp),
		"ccdDinCntrctPerson1": "",
		"ccdUidCntrctPerson1": "",
		"ccdDinCntrctPerson2": "",
		"ccdUidCntrctPerson2": "",
		"ccdDinCntrctPerson3": "",
		"ccdUidCntrctPerson3": "",
		"ccdDir4Name": "",
		"ccdDir4Desig": "",
		"ccdDir4Pan": "",
		"ccdDir4Add": "",
		"ccdDir4TelNo": "",
		"ccdDinCntrctPerson4": "",
		"ccdUidCntrctPerson4": "",
		"ccdDir4Email": "",
		"ccdDir5Name": "",
		"ccdDir5Desig": "",
		"ccdDir5Pan": "",
		"ccdDir5Add": "",
		"ccdDir5TelNo": "",
		"ccdDinCntrctPerson5": "",
		"ccdUidCntrctPerson5": "",
		"ccdDir5Email": "",
		"ccdNationalityOth": "",
		"ccdPermAddStateOth": "",
		"ccdAddStateOth": "",
		"ccdPoaFunds": _text(nse_object.ccdPoaFunds),
		"ccdPoaSecurities": is_dp_poa,
		"ccdNomFlag": nominee_flag,
		"ccdCpName": "",
		"ccdCpPan": "",
		"ccdCpEmail": "",
		"ccdCpStd": "",
		"ccdCpIsd": "",
		"ccdCpTel": "",
		"ccdCpMob": "",
		"ccdCpAdd": "",
		"ccdCpAddCity": "",
		"ccdCpAddState": "",
		"ccdCpAddStateOth": "",
		"ccdCpAddCountry": "",
		"ccdCpAddPin": "",
		"ccdPriSecDp": _text(nse_object.ccdPriSecDp),
		"ccdPriSecDp2": "",
		"ccdPriSecDp3": "",
		"ccdPriSecDp4": "",
		"ccdPriSecDp5": "",
		"ccdAcctType": _text(nse_object.ccdAcctType),
		"ccdOptForUpi": _text(nse_object.ccdOptForUpi),
		"ccdDeposName4": "",
		"ccdDeposId4": "",
		"ccdBenAcctNo4": "",
		"ccdDeposName5": "",
		"ccdDeposId5": "",
		"ccdBenAcctNo5": "",
		"ccdBankName": bankname,
		"ccdBankAcctNo": accountnumber,
		"ccdBankIfsc": ifsc,
		"ccdPriSecBnk": _text(nse_object.ccdPriSecBnk),
		"ccdBankName2": "",
		"ccdBankAcctNo2": "",
		"ccdBankIfsc2": "",
		"ccdPriSecBnk2": "",
		"ccdBankName3": "",
		"ccdBankAcctNo3": "",
		"ccdBankIfsc3": "",
		"ccdPriSecBnk3": "",
		"ccdBankName4": "",
		"ccdBankAcctNo4": "",
		"ccdBankIfsc4": "",
		"ccdPriSecBnk4": "",
		"ccdBankName5": "",
		"ccdBankAcctNo5": "",
		"ccdBankIfsc5": "",
		"ccdPriSecBnk5": ""
	})]
	logger.info(
		"NSE payload built: clientcode=%s fields=%s",
		clientcode,
		len(request_items[0]),
	)
	return {"request": request_items}, None


def _post_nse_json(url, payload, headers, timeout, service, session=None):
	"""POST JSON to NSE and normalize all transport/protocol errors."""
	client = session if session is not None else requests
	logger.info("NSE service request started: service=%s", service)
	try:
		response = client.post(
			url,
			json=payload,
			headers=headers,
			timeout=timeout,
		)
	except requests.RequestException as exc:
		logger.exception("%s connection error", service)
		return None, {
			"success": False,
			"error": str(exc),
			"msg": f"Unable to connect to {service}",
			"status": status.HTTP_502_BAD_GATEWAY,
		}

	try:
		data = response.json()
	except ValueError:
		logger.error("NSE service returned invalid JSON: service=%s", service)
		return None, {
			"success": False,
			"error": f"Invalid response from {service}",
			"msg": f"Invalid response from {service}",
			"status_code": response.status_code,
			"raw_response": response.text,
			"status": status.HTTP_502_BAD_GATEWAY,
		}

	if not isinstance(data, dict):
		logger.error("NSE service returned an unexpected response: service=%s", service)
		return None, {
			"success": False,
			"error": f"Unexpected {service} response",
			"msg": f"Unexpected {service} response",
			"status_code": response.status_code,
			"raw_response": response.text,
			"status": status.HTTP_502_BAD_GATEWAY,
		}

	response_ok = getattr(response, "ok", None)
	if response_ok is None:
		response_ok = getattr(response, "status_code", 500) < 400
	logger.info(
		"NSE service response received: service=%s http_status=%s ok=%s",
		service,
		getattr(response, "status_code", None),
		response_ok,
	)
	if not response_ok:
		logger.warning("NSE service rejected request: service=%s", service)
		error_message = data.get("msg") or data.get("message") or f"{service} request failed"
		return None, {
			"success": False,
			"error": error_message,
			"msg": error_message,
			"status_code": response.status_code,
			"provider_response": data,
			"raw_response": response.text,
			"status": status.HTTP_502_BAD_GATEWAY,
		}
	return data, None


def _authenticate_nse(credential, session=None):
	data, error = _post_nse_json(
		NSE_AUTH_URL,
		{
			"username": _text(credential.username),
			"password": _text(credential.password),
			"apiName": _text(credential.apiName),
		},
		{"Content-Type": "application/json"},
		NSE_AUTH_TIMEOUT,
		"NSE auth service",
		session=session,
	)
	if error:
		return None, error

	token = _text(data.get("token"))
	if not token:
		logger.error("NSE authentication response did not contain a token")
		return None, {
			"msg": "NSE token not received",
			"status": status.HTTP_502_BAD_GATEWAY,
		}
	logger.info("NSE authentication succeeded")
	return token, None


def _post_client_upload(token, payload, session=None):
	return _post_nse_json(
		NSE_CLIENT_UPLOAD_URL,
		payload,
		{
			"Content-Type": "application/json",
			"Authorization": f"Bearer {token}",
		},
		NSE_UPLOAD_TIMEOUT,
		"NSE client upload service",
		session=session,
	)


def _submit_nse_payload(credential, payload):
    """Reuse one HTTP connection for NSE authentication and upload."""
    with requests.Session() as session:
        token, auth_error = _authenticate_nse(credential, session=session)
        if auth_error:
            return None, auth_error
        return _post_client_upload(token, payload, session=session)


def _nse_credentials_ready(credential):
    return credential is not None and all(
        _text(getattr(credential, field, ""))
        for field in ("username", "password", "apiName")
    )


def _set_nse_push_state(client, state):
    """Store NSE completion only after the provider request succeeds."""
    if not state:
        return
    try:
        client.nse_push_at = timezone.localtime()
        client.save(update_fields=['nse_push_at'])
        logger.info(
            "NSE push state saved: clientcode=%s success=%s",
            client.clientcode,
            state,
        )
    except DatabaseError:
        logger.exception("Unable to save NSE push state: clientcode=%s", client.clientcode)


def _submit_nse(request, clientcode, client, credential, credential_username):
	"""Submit one NSE request and return a normalized result."""
	request_url = ''
	response_url = ''
	request_payload = None
	response_data = None
	try:
		payload, payload_error = _build_nse_payload(client, credential_username)
		request_payload = payload
		_save_nse_file(clientcode, "nse_request.txt", payload)
		request_url = _nse_file_url(request, clientcode, "nse_request.txt")
		logger.info(
			"NSE request prepared: clientcode=%s",
			clientcode,
		)
		if payload_error:
			response_data = {
				"success": False,
				"status": "PAYLOAD_ERROR",
				"error": payload_error,
				"msg": payload_error,
			}
			response_url = _save_nse_error_response(
				request,
				clientcode,
				payload_error,
				response_data,
			)
			return {
				"success": False,
				"status": status.HTTP_400_BAD_REQUEST,
				"msg": payload_error,
				"request_payload": request_payload,
				"response": response_data,
				"nse_response": response_data,
				"nse_request_url": request_url,
				"nse_response_url": response_url,
			}

		if not _nse_credentials_ready(credential):
			response_data = {
				"success": False,
				"status": "CREDENTIALS_NOT_CONFIGURED",
				"error": "NSE credentials are not configured completely.",
				"msg": "NSE credentials are not configured completely.",
			}
			response_url = _save_nse_error_response(
				request,
				clientcode,
				response_data["msg"],
				response_data,
			)
			return {
				"success": False,
				"status": status.HTTP_400_BAD_REQUEST,
				"msg": response_data["msg"],
				"request_payload": request_payload,
				"response": response_data,
				"nse_request_url": request_url,
				"nse_response_url": response_url,
			}

		upload_data, upload_error = _submit_nse_payload(credential, payload)
		response_data = upload_data if upload_data is not None else upload_error
		_save_nse_file(clientcode, "nse_response.txt", response_data)
		response_url = _nse_file_url(request, clientcode, "nse_response.txt")
		logger.info(
			"NSE response saved: clientcode=%s success=%s",
			clientcode,
			upload_error is None,
		)

		if upload_error:
			return {
				"success": False,
				"status": upload_error.get("status", status.HTTP_502_BAD_GATEWAY),
				"msg": upload_error.get("msg", "NSE upload failed"),
				"request_payload": request_payload,
				"response": response_data,
				"nse_response": response_data,
				"nse_request_url": request_url,
				"nse_response_url": response_url,
			}

		response_items = upload_data.get("response", []) if isinstance(upload_data, dict) else []
		if not isinstance(response_items, list):
			response_items = []
		request_success = bool(response_items) and all(
			isinstance(item, dict) and item.get("status") == "SUCCESS"
			for item in response_items
		)
		failed_items = [
			item for item in response_items
			if not isinstance(item, dict) or item.get("status") != "SUCCESS"
		]
		return {
			"success": request_success,
			"status": status.HTTP_200_OK if request_success else status.HTTP_502_BAD_GATEWAY,
			"msg": (
				"NSE request completed successfully"
				if request_success else "NSE upload failed"
			),
			"request_payload": request_payload,
			"nse_request_url": request_url,
			"nse_response_url": response_url,
			"response": upload_data,
			"nse_response": upload_data,
			"failed": failed_items,
		}

	except OSError as exc:
		logger.exception("Unable to save NSE artifact for %s", clientcode)
		response_data = {
			"success": False,
			"status": "ARTIFACT_ERROR",
			"error": str(exc),
			"msg": str(exc),
		}
		response_url = _save_nse_error_response(
			request,
			clientcode,
			response_data["msg"],
			response_data,
		)
		return {
			"success": False,
			"status": status.HTTP_500_INTERNAL_SERVER_ERROR,
			"msg": response_data["msg"],
			"request_payload": request_payload,
			"response": response_data,
			"nse_response": response_data,
			"nse_request_url": request_url,
			"nse_response_url": response_url,
		}
	except Exception as exc:
		logger.exception("Unexpected NSE provider failure: clientcode=%s", clientcode)
		response_data = {
			"success": False,
			"status": "UNEXPECTED_ERROR",
			"error": str(exc),
			"msg": str(exc),
		}
		response_url = _save_nse_error_response(
			request,
			clientcode,
			response_data["msg"],
			response_data,
		)
		return {
			"success": False,
			"status": status.HTTP_502_BAD_GATEWAY,
			"msg": response_data["msg"],
			"request_payload": request_payload,
			"response": response_data,
			"nse_request_url": request_url,
			"nse_response_url": response_url,
			"nse_response": response_data,
		}


@api_view(["POST"])
def nse_ucc_modify(request, clientcode):
	clientcode = _text(clientcode)
	if not _safe_clientcode(clientcode):
		return Response(
			{"success": False, "msg": "Invalid client code."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	company_user = _requested_company_user(request)
	if company_user is None:
		return Response(
			{"success": False, "msg": "Company not found"},
			status=status.HTTP_404_NOT_FOUND,
		)

	try:
		client = _fetch_client(clientcode, company_user)
	except Exception:
		logger.exception("Database error while loading client %s", clientcode)
		return Response(
			{"success": False, "msg": "Database error"},
			status=status.HTTP_500_INTERNAL_SERVER_ERROR,
		)
	if not client:
		return Response(
			{"success": False, "msg": "Client not found"},
			status=status.HTTP_404_NOT_FOUND,
		)

	api_not_selected = reject_if_api_not_selected(client, "NSE")
	if api_not_selected:
		return api_not_selected
	already_pushed = reject_if_already_pushed(client, "nse_push", "NSE")
	if already_pushed:
		return already_pushed
	order_blocked = reject_if_provider_order_blocked(client, "NSE")
	if order_blocked:
		return order_blocked

	credential = NseCredentials.objects.filter(user=company_user).first()
	credential_username = _text(getattr(credential, "username", ""))
	logger.info(
		"NSE credentials loaded: clientcode=%s configured=%s",
		clientcode,
		_nse_credentials_ready(credential),
	)

	result = _submit_nse(request, clientcode, client, credential, credential_username)
	_set_nse_push_state(client, result['success'])
	response_status = result['status']
	logger.info(
		"NSE UCC request completed: clientcode=%s success=%s response_status=%s",
		clientcode,
		result['success'],
		response_status,
	)
	return Response(
		{
			"success": result['success'],
			"msg": result['msg'],
			"clientcode": clientcode,
			"request_payload": result.get("request_payload"),
			"nse_response": result.get("response"),
			**{
				key: result[key]
				for key in ("nse_request_url", "nse_response_url")
				if key in result
			},
		},
		status=response_status,
	)
