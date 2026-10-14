"""BSE UCC V5 adapter using company credentials and database master values."""

import base64
import datetime as dt
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Bse,
    BseCredentials,
    BseIncomeRangeMaster,
    UserDetails,
)
from .push_tracking import (
    reject_if_api_not_selected,
    reject_if_already_pushed,
    reject_if_provider_order_blocked,
)
from .views import _requested_company_user

logger = logging.getLogger(__name__)
BSE_URL = 'https://ucc.bseindia.com/UCC_REST_API_SERVICE/UCCService.svc/AddUCCData_V5'
BSE_CREDENTIAL_FIELDS = ('MemberCode', 'UserID', 'Password')

BSE_DATE_FORMATS = (
	"%d-%m-%Y",
	"%d/%m/%Y",
	"%Y-%m-%d",
	"%Y/%m/%d",
	"%m/%d/%Y",
)

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
		return ''

	return get


def _text(value):
	return '' if value is None else str(value).strip()


def _set_bse_push_state(client, state):
    """Store BSE completion only after the provider request succeeds."""
    if not state:
        return
    try:
        client.bse_push_at = timezone.localtime()
        client.save(update_fields=['bse_push_at'])
        logger.info('BSE push state saved: clientcode=%s success=%s', client.clientcode, state)
    except DatabaseError:
        logger.exception('Unable to save BSE push state: clientcode=%s', client.clientcode)


def _yes(value):
	return _text(value).casefold() in {'1', 'true', 'yes', 'y'}


def _parse_date(value):
	value = _text(value)

	match = re.search(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", value)
	candidate = match.group() if match else value.split(" ", 1)[0]

	for fmt in BSE_DATE_FORMATS:
		try:
			return dt.datetime.strptime(candidate, fmt).date()
		except ValueError:
			continue
	return None


class BseError(Exception):
    pass


def _fetch_client(clientcode, company_user):
    logger.info(
        'BSE client lookup started: clientcode=%s company_user_id=%s',
        clientcode,
        getattr(company_user, 'id', None),
    )
    client = UserDetails.objects.filter(
        clientcode=clientcode,
        user=company_user,
    ).first()
    logger.info(
        'BSE client lookup completed: clientcode=%s found=%s',
        clientcode,
        client is not None,
    )
    return client


def _date(value, today=False):
    parsed = _parse_date(value)
    if parsed is None and today:
        parsed = timezone.localdate()
    return parsed.strftime('%d/%m/%Y') if parsed else ''


def _rsa_encrypt(value, key_path):
    """Encrypt the BSE checksum with the supplied RSA public key."""
    key_path = Path(key_path)
    if not key_path.is_file():
        logger.error('BSE public key file is missing: path=%s', key_path)
        raise BseError(f'Required BSE key file is missing: {key_path.name}')
    try:
        key = RSA.import_key(key_path.read_bytes())
        if key.has_private():
            key = key.publickey()
        encrypted = PKCS1_v1_5.new(key).encrypt(value)
    except (OSError, ValueError, IndexError, TypeError) as exc:
        logger.exception('BSE checksum encryption failed: key_file=%s', key_path.name)
        raise BseError('BSE RSA encryption failed. Check the PEM file.') from exc
    return base64.b64encode(encrypted).decode('ascii')



def _addresses(get):
    address_fields = ('addressline1', 'addressline2', 'addressline3')
    city = get('aadhaar_dist')
    state = get('aadhaar_state')
    pincode = get('aadhaar_pincode')
    country = get('aadhaar_country')
    address = ' '.join(filter(None, (get(field) for field in address_fields)))
    address = address or get('aadhaar_address')
    state = state.split('-')[-1].strip()
    return dict(
        ADDRESS1=address, ADDRESS2='',
        CITY=city, PERCITY=city, STATE=state, PERSTATE=state,
        PINCODE=pincode, PERPINCODE=pincode, COUNTRY=country,
    )


def _banks(get):
    """Return the single bank stored on UserDetails for BSE slot 1."""
    account = get('bankaccountnumber')
    ifsc = get('ifsc').upper()
    bank_name = get('bankname')
    return [{
        'name': bank_name,
        'account': account,
        'ifsc': ifsc,
        'primary': 'P',
    }]


def _build_bse_payload(client, master):
    get = _getter(client)
    logger.debug(
        'Building BSE payload: clientcode=%s master_id=%s',
        get('clientcode'),
        getattr(master, 'ID', None),
    )
    # All configured default fields come from the BSE master row.
    detail = {
        field.name: getattr(master, field.name)
        for field in Bse._meta.concrete_fields
        if not field.primary_key
    }

    clientcode = get('clientcode')
    income_value = get('annual_income')
    income_code = BseIncomeRangeMaster.objects.filter(
        income_range__iexact=income_value,
    ).values_list('income_code', flat=True).first()
    if not income_code:
        logger.warning(
            'BSE income range is not mapped; sending original value: clientcode=%s',
            clientcode,
        )
        income_code = income_value

    name = get('aadhaar_name')
    parts = name.split() if name else []
    address = _addresses(get)
    dpid = get('dpid')
    nsdl = dpid.upper().startswith('IN')
    depository_name = _text(getattr(master, 'DEPOSITORYNAME1')) if nsdl else 'CDSL'
    email = get('email')
    mobile = get('mobile')
    detail.update(address)
    detail.update(
        CLIENTCODE=clientcode.split('-')[0], PANNO=get('pan'),
        EMAIL=email,
        MOBILENUMBER=mobile,
        DEPOSITORYNAME1=depository_name, DEMANTID1=dpid[:8] if nsdl else 'CDSL',
        BENEFICIALOWNACNTNO1=dpid[8:] if nsdl else dpid,
        INCOME=_text(income_code), INCOMEDATE=_date(get('annual_income_date')),
        NETWORTH=get('networth'),
        NETWORTHDATE=_date(get('networth_date')),
        FIRSTNAME=parts[0] if len(parts) > 1 else '', MIDDLENAME=' '.join(parts[1:-1]),
        LASTNAME=parts[-1], CLIENTNAME=name, CLIENTNAMEDESCRIPTION=name,
        DATEOFBIRTH=_date(get('dob', 'aadhaar_dob')), PERCOUNTRY=address['COUNTRY'],
        OPTEDFORNOMINATION='Y' if _yes(get('nominee_check')) else 'N',
    )
    banks = _banks(get)
    if not banks:
        raise BseError('At least one bank account is required.')
    first_bank = banks[0]
    for index in range(1, 6):
        bank = first_bank if index == 1 else {}
        detail[f'BANKNAME{index}'] = bank.get('name')
        detail[f'ACCOUNTNO{index}'] = bank.get('account')
        detail[f'BANKBRANCHIFSCCODE{index}'] = bank.get('ifsc')
        detail[f'PRIMARYORSECONDARYBANK{index}'] = bank.get('primary')
    logger.debug(
        'BSE payload built: clientcode=%s field_count=%s depository=%s',
        clientcode,
        len(detail),
        depository_name,
    )
    logger.info(
        'BSE payload ready: clientcode=%s field_count=%s',
        clientcode,
        len(detail),
    )
    return {'CLIENTDETAILS_V5': [detail]}


def _save_file(request, clientcode, kind, body):
    directory = settings.BASE_DIR / 'static' / 'bse_data' / clientcode
    directory.mkdir(parents=True, exist_ok=True)
    filename = f'bse_{kind}.txt'
    path = directory / filename
    temporary_path = path.with_name(f'.{path.name}.tmp')
    temporary_path.write_text(body, encoding='utf-8')
    temporary_path.replace(path)
    logger.debug('BSE %s saved: clientcode=%s path=%s', kind, clientcode, path)
    logger.info(
        'BSE artifact saved: clientcode=%s kind=%s bytes=%s',
        clientcode,
        kind,
        len(body.encode('utf-8')),
    )
    return request.build_absolute_uri(f'/static/bse_data/{quote(clientcode, safe="")}/{filename}')


def _parse_bse_response(response):
    """Return a JSON-safe response, including non-JSON upstream bodies."""
    logger.info(
        'BSE provider response received: http_status=%s content_type=%s bytes=%s',
        response.status_code,
        response.headers.get('Content-Type', ''),
        len(response.content),
    )
    try:
        return response.json()
    except ValueError:
        logger.warning(
            'BSE returned a non-JSON response: http_status=%s',
            response.status_code,
        )
        return {
            'success': False,
            'status': 'NON_JSON_RESPONSE',
            'status_code': response.status_code,
            'msg': 'BSE returned a non-JSON response.',
            'raw_response': response.text,
        }


def _bse_credentials_ready(credential):
    return credential is not None and all(
        _text(getattr(credential, field, ''))
        for field in BSE_CREDENTIAL_FIELDS
    )


def _save_bse_error_response(
    request,
    clientcode,
    message,
    links,
    status='LOCAL_ERROR',
):
    """Save a JSON error response and return it for inline frontend display."""
    error_message = _text(message)
    error_body = {
        'success': False,
        'status': status,
        'error': error_message,
        'msg': error_message,
        'errors': [error_message],
    }
    if 'bse_response_url' not in links:
        try:
            links['bse_response_url'] = _save_file(
                request,
                clientcode,
                'response',
                json.dumps(error_body, ensure_ascii=False, indent=2, default=str),
            )
            logger.info(
                'BSE error response saved: clientcode=%s status=%s',
                clientcode,
                status,
            )
        except OSError:
            logger.exception('Unable to save BSE error response: clientcode=%s', clientcode)
    return error_body


def _submit_bse(request, clientcode, client, credential, master):
    """Submit one BSE request and return a normalized result."""
    links = {}
    request_payload = None
    try:
        payload = _build_bse_payload(client, master)
        request_payload = payload
        # Master values can contain dates/decimals. Convert those safely so
        # request generation itself does not fail before the request is saved.
        body = json.dumps(payload, separators=(',', ':'), default=str)
        body_bytes = body.encode('utf-8')
        links['bse_request_url'] = _save_file(request, clientcode, 'request', body)
        logger.info(
            'BSE request prepared: clientcode=%s payload_bytes=%s',
            clientcode,
            len(body_bytes),
        )

        # Prepare/save the request before credential validation. This allows
        # development and testing with missing or incomplete BSE credentials.
        logger.info(
            'BSE credential check: clientcode=%s configured=%s',
            clientcode,
            _bse_credentials_ready(credential),
        )
        if not _bse_credentials_ready(credential):
            error_body = _save_bse_error_response(
                request,
                clientcode,
                'BSE credentials are not configured completely.',
                links,
                status='CREDENTIALS_NOT_CONFIGURED',
            )
            return {
                'success': False,
                'status': 400,
                'msg': error_body['msg'],
                'request_payload': request_payload,
                'response': error_body,
                **links,
            }

        checksum = _rsa_encrypt(
            hashlib.sha256(body_bytes).hexdigest().encode(),
            settings.BASE_DIR / 'public.pem',
        )
        headers = {
            'MemberCode': _text(credential.MemberCode),
            'UserID': _text(credential.UserID),
            'Password': hashlib.md5(_text(credential.Password).encode()).hexdigest(),
            'Checksum': checksum,
            'Content-Type': 'application/json',
        }
        try:
            logger.info(
                'Sending BSE request: clientcode=%s endpoint=%s',
                clientcode,
                BSE_URL,
            )
            response = requests.post(BSE_URL, data=body_bytes, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise BseError(f'Unable to connect to BSE UCC service: {exc}') from exc

        result = _parse_bse_response(response)
        logger.info(
            'BSE provider response processed: clientcode=%s http_status=%s',
            clientcode,
            response.status_code,
        )
        links['bse_response_url'] = _save_file(
            request,
            clientcode,
            'response',
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
        )
        if isinstance(result, dict) and result.get('status') == 'NON_JSON_RESPONSE':
            return {
                'success': False,
                'status': 502,
                'msg': 'BSE returned a non-JSON response; it was saved as JSON.',
                'request_payload': request_payload,
                'response': result,
                **links,
            }

        rows = result.get('ResponceList') if isinstance(result, dict) else None
        success = response.ok and isinstance(rows, list) and bool(rows) and all(
            isinstance(row, dict) and row.get('STATUS') == 'S'
            for row in rows
        )
        messages = [
            _text(row.get('ERRORRESPONSE'))
            for row in rows
            if isinstance(row, dict)
        ] if isinstance(rows, list) else []
        logger.info(
            'BSE request completed: clientcode=%s success=%s',
            clientcode,
            bool(success),
        )
        return {
            'success': bool(success),
            'status': 200 if success else 502,
            'msg': '; '.join(filter(None, messages)) or (
                'BSE request completed successfully.' if success else 'BSE request rejected.'
            ),
            'request_payload': request_payload,
            'response': result,
            **links,
        }
    except BseError as exc:
        error_body = _save_bse_error_response(
            request,
            clientcode,
            exc,
            links,
            status='BSE_ERROR',
        )
        return {
            'success': False,
            'status': 400,
            'msg': str(exc),
            'request_payload': request_payload,
            'response': error_body,
            **links,
        }
    except (DatabaseError, OSError) as exc:
        error_body = _save_bse_error_response(
            request,
            clientcode,
            exc,
            links,
            status='DATABASE_OR_FILE_ERROR',
        )
        return {
            'success': False,
            'status': 500,
            'msg': 'BSE database or file operation failed.',
            'request_payload': request_payload,
            'response': error_body,
            **links,
        }
    except Exception as exc:
        error_body = _save_bse_error_response(
            request,
            clientcode,
            exc,
            links,
            status='UNEXPECTED_ERROR',
        )
        logger.exception(
            'Unexpected BSE integration error: clientcode=%s',
            clientcode,
        )
        return {
            'success': False,
            'status': 500,
            'msg': 'Unexpected BSE integration error.',
            'request_payload': request_payload,
            'response': error_body,
            **links,
        }


@api_view(['POST'])
def bse_ucc_modify(request, clientcode):
    logger.info('BSE UCC request received: clientcode=%s', clientcode)
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}', clientcode):
        logger.warning('BSE UCC rejected invalid client code: clientcode=%s', clientcode)
        return Response({'success': False, 'msg': 'Invalid client code.'}, status=400)

    client = None
    try:
        company = _requested_company_user(request)
        if company is None:
            return Response({'success': False, 'msg': 'Company not found.'}, status=404)
        logger.info(
            'BSE company resolved: clientcode=%s company_user_id=%s',
            clientcode,
            getattr(company, 'id', None),
        )

        client = _fetch_client(clientcode, company)
        if client is None:
            return Response({'success': False, 'msg': 'Client not found.'}, status=404)
        api_not_selected = reject_if_api_not_selected(client, 'BSE')
        if api_not_selected:
            return api_not_selected
        already_pushed = reject_if_already_pushed(client, 'bse_push', 'BSE')
        if already_pushed:
            return already_pushed
        order_blocked = reject_if_provider_order_blocked(client, 'BSE')
        if order_blocked:
            return order_blocked

        credential = BseCredentials.objects.filter(user=company, type='bse').first()
        logger.info(
            'BSE credentials loaded: company_user_id=%s present=%s',
            getattr(company, 'id', None),
            credential is not None,
        )

        master = Bse.objects.order_by('ID').first()
        if master is None:
            raise BseError('BSE master record not found.')
        logger.info(
            'BSE master selected: clientcode=%s master_id=%s',
            clientcode,
            getattr(master, 'ID', None),
        )

        result = _submit_bse(request, clientcode, client, credential, master)
        _set_bse_push_state(client, result['success'])
        last_response = result.get('response')
        response_status = result['status']
        logger.info(
            'BSE UCC request completed: clientcode=%s success=%s response_status=%s',
            clientcode,
            result['success'],
            response_status,
        )
        return Response(
            {
                'success': result['success'],
                'msg': result['msg'],
                'request_payload': result.get('request_payload'),
                'bse_response': last_response,
                'errors': last_response.get('errors', []) if isinstance(last_response, dict) else [],
                **{key: value for key, value in result.items() if key.endswith('_url')},
            },
            status=response_status,
        )
    except BseError as exc:
        logger.warning('BSE UCC validation failed: clientcode=%s error=%s', clientcode, exc)
        if client is not None:
            _set_bse_push_state(client, False)
        links = {}
        error_body = _save_bse_error_response(
            request,
            clientcode,
            exc,
            links,
            status='BSE_ERROR',
        )
        return Response(
            {'success': False, 'msg': str(exc), 'bse_response': error_body, **links},
            status=400,
        )
    except (DatabaseError, OSError) as exc:
        logger.exception('BSE database or file operation failed for client %s', clientcode)
        if client is not None:
            _set_bse_push_state(client, False)
        links = {}
        error_body = _save_bse_error_response(
            request,
            clientcode,
            exc,
            links,
            status='DATABASE_OR_FILE_ERROR',
        )
        return Response(
            {
                'success': False,
                'msg': 'BSE database or file operation failed.',
                'bse_response': error_body,
                **links,
            },
            status=500,
        )
    except Exception as exc:
        logger.exception('Unexpected BSE integration error: clientcode=%s', clientcode)
        if client is not None:
            _set_bse_push_state(client, False)
        links = {}
        error_body = _save_bse_error_response(
            request,
            clientcode,
            exc,
            links,
            status='UNEXPECTED_ERROR',
        )
        return Response(
            {
                'success': False,
                'msg': 'Unexpected BSE integration error.',
                'bse_response': error_body,
                **links,
            },
            status=500,
        )
