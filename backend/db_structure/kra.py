"""CVL KRA integration for the Django dashboard.

This module adapts the encrypted CVL KRA API used by the legacy integration to
this project’s company credentials and UserDetails table.  It supports:
- per-company UAT/live credentials;
- GetToken, GetPanStatus, SolicitPANDetailsFetchALLKRA and InsertUpdateKYCRecord;
- request/response artifacts protected by the authenticated file endpoint;
- separate SolicitPANDetailsFetchALLKRA request/response audit artifacts.
"""

import base64
import binascii
import datetime as dt
import io
import json
import logging
import posixpath
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import paramiko
import requests
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from django.conf import settings
from django.db import DatabaseError
from django.http import FileResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Kra,
    KraCredentials,
    KraErrorCode,
    KraGenderMaster,
    KraMaritalStatusMaster,
    KraStatusMaster,
    UserDetails,
)
from .push_tracking import reject_if_already_pushed, reject_if_api_not_selected
from .views import _requested_company_user

logger = logging.getLogger(__name__)

KRA_SFTP_PENDING_MARKER = '__KRA_SFTP_PENDING__'
KRA_SFTP_ERROR_PREFIX = '__KRA_SFTP_ERROR__: '
KRA_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
)
KRA_ERROR_CODE_PATTERN = re.compile(r'\b(?:WEBERR|ERR)-\d{3,5}\b', re.I)


def _set_kra_push_state(client, state):
    """Store the final successful KRA state and completion time."""
    if not state:
        return
    try:
        client.kra_push = True
        client.kra_push_at = timezone.localtime()
        client.save(update_fields=['kra_push', 'kra_push_at'])
    except DatabaseError:
        logger.exception('Unable to save KRA push state: clientcode=%s', client.clientcode)


def _set_kra_sftp_response(client, response):
    """Store the latest KRA SFTP result and retry state."""
    try:
        client.kra_sftp_response = _text(response)[:255]
        client.save(update_fields=['kra_sftp_response'])
    except DatabaseError:
        logger.exception('Unable to save KRA SFTP response: clientcode=%s', client.clientcode)


def _kra_sftp_retry_pending(client):
    """Return whether KRA API succeeded and only SFTP needs to be retried.

    ``kra_push_at`` is deliberately empty until both the KRA API and SFTP
    upload succeed.  The existing ``kra_sftp_response`` column carries the
    intermediate SFTP state, so a separate boolean is not needed.
    """
    if getattr(client, 'kra_push_at', None):
        return False
    value = _text(getattr(client, 'kra_sftp_response', ''))
    return bool(value)


def _kra_sftp_public_response(client):
    """Return the SFTP message without exposing the internal retry marker."""
    value = _text(getattr(client, 'kra_sftp_response', ''))
    if value.startswith(KRA_SFTP_ERROR_PREFIX):
        return value[len(KRA_SFTP_ERROR_PREFIX):]
    if value == KRA_SFTP_PENDING_MARKER:
        return 'KRA API accepted; SFTP upload is pending.'
    return value


def _legacy_response_fields(result, api_name='', source_api='', api_url='', error_code=''):
    """Add the response keys used by the legacy Flask integration."""
    result = dict(result)
    message = _text(
        result.get('admin_msg')
        or result.get('message')
        or result.get('msg')
        or result.get('error')
    )
    if message:
        result.setdefault('admin_msg', message)
        result.setdefault('msg', message)
    result.setdefault('api_name', api_name)
    result.setdefault('source_api', source_api)
    result.setdefault('api_url', api_url)
    if error_code:
        result.setdefault('error_code', error_code)
    return result


KRA_ENVIRONMENTS = {'uat', 'live'}
KRA_CREDENTIAL_FIELDS = (
    'environment',
    'token_url',
    'pan_status_url',
    'fetch_data_url',
    'insert_data_url',
    'api_key',
    'username',
    'poscode',
    'cvlkra_password',
    'aes_key',
    'sftp_host',
    'sftp_port',
    'sftp_username',
    'sftp_password',
    'sftp_base_path',
)

KRA_DEFAULT_FIELDS = (
    'APP_TYPE', 'APP_PAN_COPY', 'APP_EXMT', 'APP_EXMT_CAT', 'APP_EXMT_ID_PROOF',
    'APP_IPV_FLAG', 'APP_NATIONALITY', 'APP_RES_STATUS', 'APP_COR_CTRY',
    'APP_COR_ADD_PROOF', 'APP_PER_ADD_FLAG', 'APP_PER_CTRY', 'APP_PER_ADD_PROOF',
    'APP_DOC_PROOF', 'APP_KYC_MODE', 'APP_VER_NO', 'APP_FATCA_APPLICABLE_FLAG',
    'APP_FATCA_BIRTH_PLACE', 'APP_FATCA_BIRTH_COUNTRY', 'APP_FATCA_COUNTRY_RES',
    'APP_FATCA_COUNTRY_CITYZENSHIP',
    'APP_FATCA_DATE_DECLARATION', 'APP_MOBILE_FLG', 'APP_EMAIL_FLG', 'APP_OTP_REFNO',
    'COMPANY_CODE', 'BATCH_DATE', 'NO_OF_KYC_RECORDS', 'APP_FATCADATA_RECORDS',
    'NO_OF_ADDLDATA_RECORDS',
)
KRA_URLS = {
    'uat': {
        'token_url': 'https://krapancheck.cvlindia.com/V3/api/GetToken',
        'pan_status_url': 'https://krapancheck.cvlindia.com/V3/api/GetPanStatus',
        'fetch_data_url': 'https://krapancheck.cvlindia.com/V3/api/SolicitPANDetailsFetchALLKRA',
        'insert_data_url': 'https://krapancheck.cvlindia.com/V3/api/InsertUpdateKYCRecord',
    },
    'live': {
        'token_url': 'https://api.kracvl.com/int/api/GetToken',
        'pan_status_url': 'https://api.kracvl.com/int/api/GetPanStatus',
        'fetch_data_url': 'https://api.kracvl.com/int/api/SolicitPANDetailsFetchALLKRA',
        'insert_data_url': 'https://api.kracvl.com/int/api/InsertUpdateKYCRecord',
    },
}
KRA_CLIENT_CODE_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{1,80}$')


def _kra_error_message(code):
    """Return the editable KRA error message from the database master."""
    code = _text(code).upper()
    if not code:
        return ''
    try:
        message = KraErrorCode.objects.filter(code=code).values_list(
            'message', flat=True,
        ).first()
    except DatabaseError:
        logger.exception('KRA error-code lookup failed: code=%s', code)
        return code
    message = _text(message)
    logger.debug(
        'KRA error-code lookup: code=%s found=%s',
        code,
        bool(message),
    )
    return message or code


KRA_ARTIFACT_KINDS = {
    'request', 'response', 'fetch_request', 'fetch_response',
    'pan_status_header', 'pan_status_payload', 'pan_status_payload_enc',
    'pan_status_response', 'pan_status_check_header', 'pan_status_check_payload',
    'pan_status_check_payload_enc', 'pan_status_check_response',
    'insert_header', 'insert_payload_enc',
}


class KraError(Exception):
    """A safe, user-facing KRA integration error."""


class KraSftpError(KraError):
    """The KRA API succeeded but its document upload did not complete."""


def _text(value):
    return '' if value is None else str(value).strip()


def _embedded_provider_error_code(value):
    """Extract a KRA error code embedded in a provider message."""
    match = KRA_ERROR_CODE_PATTERN.search(_text(value))
    return match.group(0).upper() if match else ''


def _safe_clientcode(value):
    value = _text(value)
    return value if KRA_CLIENT_CODE_PATTERN.fullmatch(value) else re.sub(r'[^A-Za-z0-9_.-]', '_', value)[:80]


def _storage_dir(clientcode):
    directory = Path(settings.BASE_DIR) / 'static' / 'kra_data' / _safe_clientcode(clientcode)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _artifact_url(request, clientcode, kind):
    return request.build_absolute_uri(
        f'/api/kra_file/{quote(_safe_clientcode(clientcode), safe="")}/{kind}/'
    )


def _save_artifact(request, clientcode, kind, content):
    filename = f'kra_{kind}.txt'
    path = _storage_dir(clientcode) / filename
    temporary_path = path.with_name(f'.{path.name}.tmp')
    temporary_path.write_text(_text(content), encoding='utf-8')
    temporary_path.replace(path)
    logger.info(
        'KRA artifact saved: clientcode=%s kind=%s bytes=%s',
        clientcode,
        kind,
        path.stat().st_size,
    )
    return _artifact_url(request, clientcode, kind)


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _decode_aes_key(value):
    raw = _text(value)
    if not raw:
        raise KraError('KRA AES key is required.')
    try:
        key = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise KraError('KRA AES key must be valid base64.') from exc
    if len(key) not in {16, 24, 32}:
        raise KraError('KRA AES key must decode to 16, 24, or 32 bytes.')
    return key


def _pkcs7_pad(value):
    padding = AES.block_size - (len(value) % AES.block_size)
    return value + bytes([padding]) * padding


def _pkcs7_unpad(value):
    if not value:
        raise KraError('KRA response is empty after decryption.')
    padding = value[-1]
    if padding < 1 or padding > AES.block_size or value[-padding:] != bytes([padding]) * padding:
        raise KraError('KRA response has invalid encryption padding.')
    return value[:-padding]


def _encrypt_string(aes_key, payload):
    key = _decode_aes_key(aes_key)
    iv = get_random_bytes(AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(_pkcs7_pad(json.dumps(payload).encode('utf-8')))
    return f'{base64.b64encode(iv).decode()}:{base64.b64encode(encrypted).decode()}'


def _decode_b64(value):
    value = _text(value)
    value += '=' * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value)


def _decrypt_string(aes_key, encrypted_response):
    key = _decode_aes_key(aes_key)
    value = _text(encrypted_response).strip().strip('"')
    if ':' not in value:
        raise KraError('KRA returned an invalid encrypted response.')
    iv_text, encrypted_text = value.split(':', 1)
    cipher = AES.new(key, AES.MODE_CBC, _decode_b64(iv_text))
    decrypted = cipher.decrypt(_decode_b64(encrypted_text))
    cleaned = re.sub(r'[\x00-\x1f]', '', _pkcs7_unpad(decrypted).decode('utf-8'))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise KraError('KRA returned an invalid JSON response.') from exc


def _dictify(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], dict) else {}
    if isinstance(value, str):
        try:
            return _dictify(json.loads(value))
        except (TypeError, ValueError):
            return {}
    return {}


def _response_error(response):
    return {
        'success': False,
        'status_code': response.status_code,
        'message': f'KRA provider returned HTTP {response.status_code}.',
        'raw_response': response.text[:2000],
    }


def _post_encrypted(url, aes_key, payload, headers, timeout=90, encrypted_payload=None):
    """POST an encrypted KRA payload.

    ``encrypted_payload`` is optional so a caller can persist the exact
    encrypted request before sending it.  This is used for the legacy KRA
    fetch audit files; all existing callers continue to encrypt internally.
    """
    encrypted_payload = encrypted_payload or _encrypt_string(aes_key, payload)
    logger.info('KRA provider request started: url=%s', url)
    response = requests.post(
        url,
        headers={**headers, 'content-type': 'application/json'},
        data=json.dumps(encrypted_payload),
        timeout=timeout,
    )
    try:
        decoded = _decrypt_string(aes_key, response.text)
    except KraError:
        try:
            decoded = response.json()
        except ValueError:
            decoded = _response_error(response)
    if not response.ok and not isinstance(decoded, dict):
        decoded = _response_error(response)
    logger.info(
        'KRA provider response received: url=%s status=%s decoded=%s',
        url,
        response.status_code,
        isinstance(decoded, dict),
    )
    return decoded, encrypted_payload, response


def _credential_payload(credential):
    return {field: _text(getattr(credential, field, '')) for field in KRA_CREDENTIAL_FIELDS}


def _fetch_kra_defaults():
    '''Load editable static KRA payload values from the kra table.'''
    try:
        defaults = Kra.objects.order_by('id').values(*KRA_DEFAULT_FIELDS).first() or {}
        logger.debug(
            'KRA defaults loaded: configured_fields=%s',
            [field for field in KRA_DEFAULT_FIELDS if _text(defaults.get(field))],
        )
        return defaults
    except DatabaseError:
        logger.exception('Unable to load KRA defaults from kra table')
        return {}


def _effective_urls(credential):
    defaults = KRA_URLS.get(_text(credential.environment).lower(), KRA_URLS['uat'])
    return {
        field: _text(getattr(credential, field, '')) or defaults[field]
        for field in ('token_url', 'pan_status_url', 'fetch_data_url', 'insert_data_url')
    }


def _validate_credential(credential):
    missing = [
        field for field in ('api_key', 'username', 'poscode', 'cvlkra_password', 'aes_key')
        if not _text(getattr(credential, field, ''))
    ]
    if missing:
        raise KraError(f'KRA credentials are not configured completely: {", ".join(missing)}.')
    _decode_aes_key(credential.aes_key)
    urls = _effective_urls(credential)
    if any(not urls[field] for field in urls):
        raise KraError('KRA API URLs are not configured completely.')
    return urls


def _parse_date(value):
    raw = _text(value)
    if not raw:
        return ''
    formats = (
        '%d/%m/%Y %I:%M:%S %p', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d',
        '%d-%m-%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d', '%d%m%Y', '%Y%m%d',
    )
    for pattern in formats:
        try:
            return dt.datetime.strptime(raw, pattern).strftime('%d/%m/%Y')
        except ValueError:
            continue
    return ''


def _clean_father(value):
    value = _text(value)
    return re.sub(r'^(?:D/O|W/O|S/O)\s*[, ]*', '', value, flags=re.I).replace(':', '').strip()


def _address_parts(client):
    source = _text(getattr(client, 'aadhaar_address', '')) or ' '.join(
        _text(getattr(client, field, '')) for field in ('addressline1', 'addressline2', 'addressline3')
    ).strip()
    words = source.split()
    parts = ['', '', '']
    for word in words:
        placed = False
        for index in range(3):
            candidate = f'{parts[index]} {word}'.strip()
            if len(candidate) <= 55:
                parts[index] = candidate
                placed = True
                break
        if not placed:
            break
    return parts


def _lookup_master_code(model, name_field, code_field, value):
    raw = _text(value)
    if not raw:
        return ''
    try:
        code = model.objects.filter(
            **{f'{name_field}__iexact': raw},
        ).values_list(code_field, flat=True).first()
    except DatabaseError:
        logger.exception('Unable to load KRA lookup value: table=%s field=%s', model._meta.db_table, name_field)
        return ''
    return _text(code).upper()


def _gender(value):
    raw = _text(value)
    database_code = _lookup_master_code(KraGenderMaster, 'gender', 'gender_code', raw)
    if database_code:
        return database_code
    # Accept a value that is already a provider code when the master table is
    # not populated yet; descriptive values still remain empty rather than
    # being sent as invalid KRA codes.
    return raw.upper() if re.fullmatch(r'[A-Z]', raw.upper()) else ''

def _marital_status(value):
    raw = _text(value)
    database_code = _lookup_master_code(
        KraMaritalStatusMaster,
        'marital_status',
        'marital_code',
        raw,
    )
    if database_code:
        return database_code
    return raw.upper() if re.fullmatch(r'[A-Z0-9]{1,10}', raw.upper()) else ''

def _status_payload(value):
    value = _dictify(value)
    nested = _dictify(value.get('resdtls', value))
    inquiry = _dictify(nested.get('APP_PAN_INQ', nested.get('app_pan_inq', {})))
    return value, inquiry


def _provider_message(value):
    data = _dictify(value)
    unknown_code = ''
    for key in (
        'error_code', 'ERROR_CODE', 'ERR_CODE', 'APP_ERROR_CODE',
        'code', 'CODE',
    ):
        code = _text(data.get(key)).upper()
        if code:
            mapped = _kra_error_message(code)
            if mapped != code:
                return mapped
            unknown_code = code
    for key in (
        'error_message', 'message', 'ERROR_MSG', 'ERR_MSG',
        'error_description', 'ERROR_DESCRIPTION', 'description',
        'APP_STATUS_DESC', 'APP_ERROR_DESC',
    ):
        message = _text(data.get(key))
        if message:
            embedded_code = _embedded_provider_error_code(message)
            if embedded_code:
                mapped = _kra_error_message(embedded_code)
                return mapped if mapped != embedded_code else message
            return message
    if unknown_code:
        return unknown_code
    error = data.get('ERROR')
    if isinstance(error, list):
        messages = [_provider_message(item) for item in error]
        return ' | '.join(item for item in messages if item)
    if isinstance(error, dict):
        return _provider_message(error)
    if isinstance(error, str):
        error_text = _text(error)
        embedded_code = _embedded_provider_error_code(error_text)
        if embedded_code:
            mapped = _kra_error_message(embedded_code)
            return mapped if mapped != embedded_code else error_text
        return error_text
    nested = _dictify(data.get('resdtls'))
    if nested and nested != data:
        return _provider_message(nested)
    return ''


def _provider_error(value):
    """Return a provider error code when a KRA response reports one."""
    data = _dictify(value)
    for key in (
        'error_code', 'ERROR_CODE', 'ERR_CODE', 'APP_ERROR_CODE',
        'code', 'CODE',
    ):
        code = _text(data.get(key)).upper()
        if code:
            return code
    message = _provider_message(data)
    embedded_code = _embedded_provider_error_code(message)
    if embedded_code:
        return embedded_code
    error = data.get('ERROR')
    if isinstance(error, list):
        for item in error:
            code = _provider_error(item)
            if code:
                return code
    if isinstance(error, dict):
        code = _provider_error(error)
        if code:
            return code
    if isinstance(error, str):
        embedded_code = _embedded_provider_error_code(error)
        if embedded_code:
            return embedded_code
    nested = _dictify(data.get('resdtls'))
    if nested and nested != data:
        return _provider_error(nested)
    return ''


def _has_provider_error(value):
    """Detect CVL error containers even when they have no error code."""
    data = _dictify(value)
    error = data.get('ERROR')
    if error not in (None, '', [], {}):
        return True
    if _provider_error(data):
        return True
    nested = _dictify(data.get('resdtls'))
    return bool(nested and nested != data and _has_provider_error(nested))


def _kra_status_was_updated_today(inquiry):
    """Match the legacy flow's post-insert status verification rule."""
    update_status = _text(inquiry.get('APP_UPDT_STATUS'))
    modified_date = _parse_date(inquiry.get('APP_MODDT'))
    return update_status.endswith('1') and modified_date == timezone.localdate().strftime('%d/%m/%Y')


def _select_kra(app_status, modification_status='', modification_date=''):
    code = _text(app_status).zfill(3)
    modification_code = _text(modification_status).zfill(3)

    # CVL's legacy integration treats a 004 PAN status followed by an
    # un-dated 005 update status as a fresh CVLKRA record. Keep that special
    # case before the generic status-prefix mapping.
    if (
        code[1:] == '04'
        and modification_code[1:] == '05'
        and not _text(modification_date)
    ):
        return '01', 'CVLKRA'

    try:
        exact = KraStatusMaster.objects.filter(app_status=code).first()
        if exact:
            return _text(exact.update_flag), _text(exact.kra_code)

        prefix = KraStatusMaster.objects.filter(
            app_status=code[:1],
        ).first()
        if prefix and not code.endswith('0'):
            return _text(prefix.update_flag), _text(prefix.kra_code)

        default = KraStatusMaster.objects.filter(app_status='*').first()
        if default:
            return _text(default.update_flag), _text(default.kra_code)
    except DatabaseError:
        logger.exception('Unable to load KRA status mapping from kra_status_master')

    # Safe fallback while the lookup table is unavailable.
    if code.startswith('1') and not code.endswith('0'):
        return '99', 'NDML'
    if (code.startswith('2') or code.startswith('3')) and not code.endswith('0'):
        return '99', 'CAMS'
    if code.startswith('4') and not code.endswith('0'):
        return '99', 'KARVY'
    if code.startswith('5') and not code.endswith('0'):
        return '99', 'BSE'
    if code.startswith('6') and not code.endswith('0'):
        return '99', 'KFIN'
    if code.startswith('0') and code not in {'004', '005'} and not code.endswith('0'):
        return '02', 'CVLKRA'
    return '01', 'CVLKRA'


def _local_document_path(source, label):
    """Resolve a configured local KRA document without deleting anything."""
    source = _text(source)
    if not source:
        return None

    parsed = urlsplit(source)
    if parsed.scheme in {'http', 'https'}:
        return None

    raw_path = unquote(parsed.path if parsed.scheme == 'file' else source)
    candidates = [Path(raw_path)]
    relative_path = raw_path.lstrip('/')
    candidates.extend((
        Path(settings.BASE_DIR) / relative_path,
        Path(settings.BASE_DIR) / 'static' / relative_path,
    ))
    if relative_path.startswith('static/'):
        candidates.append(Path(settings.BASE_DIR) / relative_path)

    for path in candidates:
        if path.is_file():
            return path
    raise KraSftpError(f'KRA {label} file was not found.')


def _document_bytes(source, label):
    """Read a KRA document from an HTTP URL or a local project path."""
    source = _text(source)
    if not source:
        return b''

    parsed = urlsplit(source)
    if parsed.scheme in {'http', 'https'}:
        try:
            response = requests.get(source, timeout=90)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise KraSftpError(f'Unable to download KRA {label}: {exc}') from exc
        return response.content

    path = _local_document_path(source, label)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise KraSftpError(f'Unable to read KRA {label}: {exc}') from exc


def _sftp_mkdir_p(sftp, directory):
    normalized = posixpath.normpath(directory)
    current = '/' if normalized.startswith('/') else ''
    for part in normalized.split('/'):
        if not part or part == '.':
            continue
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def _upload_kra_documents(client, credential):
    """Upload configured KRA PDF/XML documents to the CVL KRA SFTP folder."""
    documents = (
        ('pdf_file_kra', 'PDF', 'pdf'),
        ('aadhar_xml', 'xml', 'xml'),
    )
    configured = [
        (field, extension, label, _text(getattr(client, field, '')))
        for field, extension, label in documents
        if _text(getattr(client, field, ''))
    ]
    if not configured:
        return {
            'attempted': False,
            'success': True,
            'status': 'NOT_REQUIRED',
            'uploaded': [],
            'message': 'No KRA PDF or XML document was configured for this client.',
        }

    missing = [
        field for field in ('sftp_host', 'sftp_username', 'sftp_password')
        if not _text(getattr(credential, field, ''))
    ]
    if missing:
        raise KraSftpError(
            'KRA SFTP credentials are not configured completely: '
            + ', '.join(missing) + '.'
        )
    try:
        port = int(_text(getattr(credential, 'sftp_port', '22')) or '22')
    except ValueError as exc:
        raise KraSftpError('KRA SFTP port must be a number.') from exc

    host = _text(credential.sftp_host)
    username = _text(credential.sftp_username)
    password = _text(credential.sftp_password)
    base_path = _text(getattr(credential, 'sftp_base_path', '.')) or '.'
    remote_directory = posixpath.join(
        base_path,
        timezone.localdate().strftime('%d%m%Y'),
        'CVLKRA',
    )
    pan = _text(getattr(client, 'pan', '')).upper()
    if not pan:
        raise KraSftpError('PAN is required before uploading KRA documents.')

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sftp = None
    uploaded = []
    cleanup_errors = []
    try:
        logger.info('Connecting to KRA SFTP: host=%s port=%s', host, port)
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=30,
            auth_timeout=30,
            banner_timeout=30,
        )
        sftp = ssh.open_sftp()
        _sftp_mkdir_p(sftp, remote_directory)
        for _, extension, label, source in configured:
            content = _document_bytes(source, label)
            local_path = _local_document_path(source, label)
            remote_path = posixpath.join(remote_directory, f'{pan}.{extension}')
            sftp.putfo(io.BytesIO(content), remote_path)
            sftp.stat(remote_path)
            document_result = {
                'document': label,
                'remote_path': remote_path,
                'bytes': len(content),
            }
            if local_path is not None:
                try:
                    local_path.unlink()
                    document_result['local_removed'] = True
                    logger.info(
                        'Removed local KRA document after verified upload: path=%s',
                        local_path,
                    )
                except OSError as exc:
                    cleanup_error = f'{local_path}: {exc}'
                    cleanup_errors.append(cleanup_error)
                    document_result['local_removed'] = False
                    document_result['local_cleanup_error'] = str(exc)
                    logger.warning(
                        'KRA document uploaded but local cleanup failed: path=%s error=%s',
                        local_path,
                        exc,
                    )
            else:
                document_result['local_removed'] = False
                document_result['local_cleanup'] = 'Skipped because the source is a remote URL.'
            uploaded.append(document_result)
        logger.info(
            'KRA documents uploaded: clientcode=%s documents=%s',
            client.clientcode,
            [item['document'] for item in uploaded],
        )
        status_text = 'UPLOADED_WITH_CLEANUP_ERRORS' if cleanup_errors else 'UPLOADED'
        message = 'KRA documents uploaded successfully.'
        if cleanup_errors:
            message += ' Some local files could not be removed: ' + ' | '.join(cleanup_errors)
        return {
            'attempted': True,
            'success': True,
            'status': status_text,
            'remote_directory': remote_directory,
            'uploaded': uploaded,
            'message': message,
        }
    except KraError:
        raise
    except (OSError, paramiko.SSHException, paramiko.SFTPError) as exc:
        raise KraSftpError(f'KRA SFTP document upload failed: {exc}') from exc
    finally:
        if sftp is not None:
            sftp.close()
        ssh.close()


def _build_pan_status_payload(client, credential):
    return {'pan': _text(client.pan).upper(), 'poscode': _text(credential.poscode)}


def _build_fetch_payload(client, credential, kra_type):
    return {
        'APP_REQ_ROOT': {
            'APP_PAN_INQ': {
                'APP_PAN_NO': _text(client.pan).upper(),
                'APP_DOB_INCORP': _parse_date(getattr(client, 'aadhaar_dob', '')),
                'APP_POS_CODE': _text(credential.poscode),
                'APP_RTA_CODE': _text(credential.poscode),
                'APP_KRA_CODE': kra_type,
                'FETCH_TYPE': 'I',
            },
        },
    }


def _build_insert_payload(client, credential, kra_type, update_flag, fetched=None, defaults=None):
    cor1, cor2, cor3 = _address_parts(client)
    dob = _parse_date(getattr(client, 'aadhaar_dob', ''))
    fetched = _dictify(fetched)
    fetched_uid = _text(fetched.get('APP_UID_NO'))
    uid = fetched_uid if fetched_uid and (len(fetched_uid) == 12 or (len(fetched_uid) == 4 and fetched_uid.isdigit())) else _text(getattr(client, 'aadhaar_no', ''))
    name = _text(getattr(client, 'aadhaar_name', '')) or _text(getattr(client, 'client_name', ''))
    state = _text(getattr(client, 'aadhaar_state', ''))
    city = _text(getattr(client, 'aadhaar_dist', ''))
    pin = _text(getattr(client, 'aadhaar_pincode', ''))
    today = timezone.localtime().strftime('%d/%m/%Y')
    defaults = defaults or {}
    static = lambda field, fallback='': _text(defaults.get(field)) or fallback
    poscode = _text(getattr(credential, 'poscode', ''))
    fatca_applicable = static('APP_FATCA_APPLICABLE_FLAG', 'N')
    fatca_birth_country = static(
        'APP_FATCA_BIRTH_COUNTRY',
        'IN' if fatca_applicable.casefold() != 'n' else '',
    )
    holder_type = _text(getattr(client, 'account_holder_type', 'individual')).casefold()
    entity_type = 'N' if holder_type in {'corporate', 'company', 'non-individual'} else 'I'
    father_name = '' if entity_type == 'N' else _clean_father(getattr(client, 'fathername', ''))
    gender = '' if entity_type == 'N' else _gender(getattr(client, 'aadhaar_gender', ''))
    marital_status = '' if entity_type == 'N' else _marital_status(getattr(client, 'marital_status', ''))
    kyc_data = {
        'APP_UPDTFLG': update_flag,
        'APP_POS_CODE': poscode,
        'APP_KRA_CODE': kra_type,
        'APP_TYPE': static('APP_TYPE', entity_type),
        'APP_NO': '',
        'APP_DATE': today,
        'APP_PAN_NO': _text(client.pan).upper(),
        'APP_PAN_COPY': static('APP_PAN_COPY', 'Y'),
        'APP_EXMT': static('APP_EXMT', 'N'),
        'APP_EXMT_CAT': static('APP_EXMT_CAT', ''),
        'APP_EXMT_ID_PROOF': static('APP_EXMT_ID_PROOF', '02'),
        'APP_IPV_FLAG': static('APP_IPV_FLAG', 'E'),
        'APP_IPV_DATE': today,
        'APP_GEN': gender,
        'APP_NAME': name,
        'APP_F_NAME': father_name,
        'APP_REGNO': '',
        'APP_DOB_INCORP': dob,
        'APP_COMMENCE_DT': '',
        'APP_NATIONALITY': static('APP_NATIONALITY', '01'),
        'APP_OTH_NATIONALITY': '',
        'APP_COMP_STATUS': '',
        'APP_OTH_COMP_STATUS': '',
        'APP_RES_STATUS': static('APP_RES_STATUS', 'R'),
        'APP_RES_STATUS_PROOF': '',
        'APP_UID_NO': uid,
        'APP_COR_ADD1': cor1,
        'APP_COR_ADD2': cor2,
        'APP_COR_ADD3': cor3,
        'APP_COR_CITY': city,
        'APP_COR_PINCD': pin,
        'APP_COR_STATE': state,
        'APP_COR_CTRY': static('APP_COR_CTRY', '101'),
        'APP_OFF_ISD': '', 'APP_OFF_STD': '', 'APP_OFF_NO': '',
        'APP_RES_ISD': '', 'APP_RES_STD': '', 'APP_RES_NO': '',
        'APP_MOB_ISD': '',
        'APP_MOB_NO': _text(getattr(client, 'mobile', '')),
        'APP_FAX_ISD': '', 'APP_FAX_STD': '', 'APP_FAX_NO': '',
        'APP_EMAIL': _text(getattr(client, 'email', '')),
        'APP_COR_ADD_PROOF': static('APP_COR_ADD_PROOF', '31'), 'APP_COR_ADD_REF': '', 'APP_COR_ADD_DT': '',
        'APP_PER_ADD_FLAG': static('APP_PER_ADD_FLAG', 'Y'),
        'APP_PER_ADD1': cor1, 'APP_PER_ADD2': cor2, 'APP_PER_ADD3': cor3,
        'APP_PER_CITY': city, 'APP_PER_PINCD': pin, 'APP_PER_STATE': state, 'APP_PER_CTRY': static('APP_PER_CTRY', '101'),
        'APP_PER_ADD_PROOF': static('APP_PER_ADD_PROOF', '31'), 'APP_PER_ADD_REF': '', 'APP_PER_ADD_DT': '',
        'APP_INCOME': _text(getattr(client, 'annual_income', '')),
        'APP_OCC': _text(getattr(client, 'occupation', '')),
        'APP_OTH_OCC': '',
        'APP_POL_CONN': '',
        'APP_DOC_PROOF': static('APP_DOC_PROOF', 'S'),
        'APP_INTERNAL_REF': _text(getattr(client, 'clientcode', '')),
        'APP_BRANCH_CODE': '',
        'APP_MAR_STATUS': marital_status,
        'APP_NETWRTH': _text(getattr(client, 'networth', '')),
        'APP_NETWORTH_DT': _parse_date(getattr(client, 'networth_date', '')),
        'APP_INCORP_PLC': city,
        'APP_OTHERINFO': '', 'APP_FILLER1': '', 'APP_FILLER2': '', 'APP_FILLER3': '',
        'APP_IPV_NAME': '', 'APP_IPV_DESG': '', 'APP_IPV_ORGAN': '',
        'APP_KYC_MODE': static('APP_KYC_MODE', '5'), 'APP_VER_NO': static('APP_VER_NO', 'V28'),
        'APP_VID_NO': '', 'APP_UID_TOKEN': '', 'APP_AUTH_NAME': '',
        'APP_AUTH_EMAIL': '', 'APP_AUTH_EMAIL1': '', 'APP_AUTH_EMAIL2': '', 'APP_AUTH_MOBILE': '',
        'APP_AUTH_FPICONSENT': '', 'APP_AUTH_UBOCONSENT': '',
        'APP_FATCA_APPLICABLE_FLAG': fatca_applicable,
        'APP_FATCA_BIRTH_PLACE': static('APP_FATCA_BIRTH_PLACE', city),
        'APP_FATCA_BIRTH_COUNTRY': fatca_birth_country, 'APP_FATCA_COUNTRY_RES': static('APP_FATCA_COUNTRY_RES', 'IN'),
        'APP_FATCA_COUNTRY_CITYZENSHIP': static('APP_FATCA_COUNTRY_CITYZENSHIP', ''), 'APP_FATCA_DATE_DECLARATION': static('APP_FATCA_DATE_DECLARATION', today),
        'APP_MOBILE_FLG': static('APP_MOBILE_FLG', 'N'), 'APP_EMAIL_FLG': static('APP_EMAIL_FLG', 'N'), 'APP_OTP_REFNO': static('APP_OTP_REFNO', 'N'),
        'APP_PERM_DISTRICT': city, 'APP_CORR_DISTRICT': city,
    }
    return {
        'ROOT': {
            'HEADER': {'COMPANY_CODE': static('COMPANY_CODE', poscode), 'BATCH_DATE': static('BATCH_DATE', today)},
            'KYCDATA': kyc_data,
            'FOOTER': {'NO_OF_KYC_RECORDS': static('NO_OF_KYC_RECORDS', '1'), 'APP_FATCADATA_RECORDS': static('APP_FATCADATA_RECORDS', ''), 'NO_OF_ADDLDATA_RECORDS': static('NO_OF_ADDLDATA_RECORDS', '0')},
        },
    }


def _finish(
    request,
    clientcode,
    result,
    request_payload=None,
    response_payload=None,
    http_status=status.HTTP_200_OK,
    artifact_urls=None,
    api_name='',
    source_api='',
    api_url='',
    error_code='',
):
    result = _legacy_response_fields(
        result,
        api_name=api_name,
        source_api=source_api,
        api_url=api_url,
        error_code=error_code,
    )
    request_artifact = request_payload if request_payload is not None else {
        'clientcode': clientcode,
        'message': result.get('message', 'KRA request was not generated.'),
    }
    response_artifact = (
        dict(response_payload)
        if isinstance(response_payload, dict)
        else response_payload if response_payload is not None else dict(result)
    )
    # Keep request and response data separate for the frontend modal.
    result['request_payload'] = request_payload
    result['kra_response'] = response_artifact
    result['kra_request_url'] = _save_artifact(
        request, clientcode, 'request', _json_text(request_artifact),
    )
    result['kra_response_url'] = _save_artifact(
        request, clientcode, 'response', _json_text(response_artifact),
    )
    for key, value in (artifact_urls or {}).items():
        if value:
            result[key] = value
    return Response(result, status=http_status)


def _kra_error_artifact(error_response, provider_response=None):
    """Keep the actual local error alongside any provider response."""
    artifact = dict(error_response)
    if provider_response is not None:
        artifact['provider_response'] = provider_response
    return artifact


def _kra_sftp_retry_payload(clientcode):
    return {
        'clientcode': clientcode,
        'sftp_retry': True,
        'message': 'KRA API already succeeded; retrying SFTP only.',
    }


def _kra_sftp_retry_error(client, error_message):
    return {
        'success': False,
        'status': 'KRA_SFTP_ERROR',
        'sftp_retry': True,
        'error': error_message,
        'message': error_message,
        'msg': error_message,
        'errors': [error_message],
        'kra_sftp_response': _kra_sftp_public_response(client),
        'kra_push': bool(getattr(client, 'kra_push', False)),
        'kra_push_at': getattr(client, 'kra_push_at', None),
    }


def _finish_kra_sftp_retry(request, clientcode, result, http_status):
    retry_payload = _kra_sftp_retry_payload(clientcode)
    return _finish(
        request,
        clientcode,
        result,
        request_payload=retry_payload,
        response_payload=result,
        http_status=http_status,
        api_name='KRA SFTP upload',
        source_api='CVL KRA SFTP document upload',
    )


@api_view(['GET', 'POST'])
def kra_credentials_view(request):
    company = _requested_company_user(request)
    if company is None:
        return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    environment = _text(
        request.query_params.get('environment') if request.method == 'GET' else request.data.get('environment')
    ).lower() or 'uat'
    if environment not in KRA_ENVIRONMENTS:
        return Response({'error': 'Environment must be uat or live.'}, status=status.HTTP_400_BAD_REQUEST)
    credential = KraCredentials.objects.filter(user=company, environment=environment).first()
    if request.method == 'GET':
        values = _credential_payload(credential) if credential else {
            'environment': environment,
            **KRA_URLS[environment],
            **{
                'api_key': '',
                'username': '',
                'poscode': '',
                'cvlkra_password': '',
                'aes_key': '',
                'sftp_host': '',
                'sftp_port': '22',
                'sftp_username': '',
                'sftp_password': '',
                'sftp_base_path': '.',
            },
        }
        values['environment'] = environment
        for field, value in KRA_URLS[environment].items():
            values[field] = values.get(field) or value
        return Response({'user_id': company.id, 'company': company.username, 'credentials': values})

    if request.data.get('sftp_only'):
        if credential is None:
            return Response(
                {'error': f'KRA {environment} API credentials must be saved before SFTP credentials.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sftp_values = {
            field: _text(request.data.get(field, ''))
            for field in ('sftp_host', 'sftp_port', 'sftp_username', 'sftp_base_path')
            if field in request.data
        }
        if 'sftp_password' in request.data and _text(request.data.get('sftp_password')):
            sftp_values['sftp_password'] = _text(request.data.get('sftp_password'))
        if not sftp_values.get('sftp_port'):
            sftp_values['sftp_port'] = '22'
        KraCredentials.objects.filter(pk=credential.pk).update(**sftp_values)
        credential.refresh_from_db()
        logger.info('KRA SFTP credentials saved: user_id=%s environment=%s', company.id, environment)
        return Response({
            'success': True,
            'user_id': company.id,
            'company': company.username,
            'credentials': _credential_payload(credential),
        })

    values = {field: _text(request.data.get(field, '')) for field in KRA_CREDENTIAL_FIELDS if field != 'environment'}
    values['environment'] = environment
    if credential:
        for secret in ('api_key', 'cvlkra_password', 'aes_key', 'sftp_password'):
            if not values.get(secret):
                values.pop(secret, None)
    missing = [field for field in ('api_key', 'username', 'poscode', 'cvlkra_password', 'aes_key') if not values.get(field) and not (credential and getattr(credential, field, ''))]
    if missing:
        return Response({'error': f'KRA credentials are required: {", ".join(missing)}.'}, status=status.HTTP_400_BAD_REQUEST)
    aes_key = values.get('aes_key') or getattr(credential, 'aes_key', '')
    try:
        _decode_aes_key(aes_key)
    except KraError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    for url_field, default_url in KRA_URLS[environment].items():
        values[url_field] = values.get(url_field) or default_url
    credential, _ = KraCredentials.objects.update_or_create(
        user=company, environment=environment, defaults=values,
    )
    logger.info('KRA credentials saved: user_id=%s environment=%s', company.id, environment)
    return Response({'success': True, 'user_id': company.id, 'company': company.username, 'credentials': _credential_payload(credential)})


@api_view(['GET'])
def kra_file(request, clientcode, kind):
    if kind not in KRA_ARTIFACT_KINDS or not KRA_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    company = _requested_company_user(request)
    if company is None:
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not (request.user.is_staff or request.user.is_superuser) and not UserDetails.objects.filter(clientcode=clientcode, user=request.user).exists():
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    path = _storage_dir(clientcode) / f'kra_{kind}.txt'
    if not path.is_file():
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    return FileResponse(path.open('rb'), as_attachment=True, filename=path.name, content_type='text/plain')


@api_view(['POST'])
def kra_ucc_modify(request, clientcode):
    logger.info('KRA request started: clientcode=%s', clientcode)
    if not KRA_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({'success': False, 'message': 'Invalid client code.'}, status=status.HTTP_400_BAD_REQUEST)
    company = _requested_company_user(request)
    if company is None:
        return Response({'success': False, 'message': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    client = UserDetails.objects.filter(clientcode=clientcode, user=company).first()
    if client is None:
        return Response({'success': False, 'message': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
    api_not_selected = reject_if_api_not_selected(client, 'KRA')
    if api_not_selected:
        return api_not_selected
    environment = _text(
        request.data.get('environment')
        or request.query_params.get('environment')
        or 'uat'
    ).lower()

    # If the KRA API already accepted the record but document SFTP failed,
    # retry only SFTP.  Running GetToken/GetPanStatus/InsertUpdateKYCRecord
    # again could create a duplicate KRA request.
    if _kra_sftp_retry_pending(client):
        logger.info(
            'KRA SFTP-only retry started: clientcode=%s environment=%s previous_status=%s',
            clientcode,
            environment,
            _text(getattr(client, 'kra_sftp_response', '')),
        )
        credential = KraCredentials.objects.filter(
            user=company,
            environment=environment,
        ).first()
        if credential is None:
            error_message = f'KRA {environment} credentials are not configured.'
            _set_kra_sftp_response(client, f'{KRA_SFTP_ERROR_PREFIX}{error_message}')
            return _finish_kra_sftp_retry(
                request,
                clientcode,
                _kra_sftp_retry_error(client, error_message),
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            sftp_response = _upload_kra_documents(client, credential)
        except KraSftpError as exc:
            error_message = str(exc)
            _set_kra_sftp_response(client, f'{KRA_SFTP_ERROR_PREFIX}{error_message}')
            logger.warning(
                'KRA SFTP-only retry failed: clientcode=%s error=%s',
                clientcode,
                error_message,
            )
            return _finish_kra_sftp_retry(
                request,
                clientcode,
                _kra_sftp_retry_error(client, error_message),
                status.HTTP_502_BAD_GATEWAY,
            )

        _set_kra_sftp_response(client, sftp_response.get('status', 'UPLOADED'))
        _set_kra_push_state(client, True)
        logger.info(
            'KRA SFTP-only retry completed: clientcode=%s status=%s uploaded_count=%s',
            clientcode,
            sftp_response.get('status'),
            len(sftp_response.get('uploaded', [])),
        )
        retry_result = {
            'success': True,
            'status': 'KRA_SFTP_RETRY_SUCCESS',
            'sftp_retry': True,
            'message': 'KRA documents uploaded successfully on retry.',
            'document_upload': sftp_response,
            'kra_sftp_response': _kra_sftp_public_response(client),
            'sftp_response': _kra_sftp_public_response(client),
            'kra_push': bool(getattr(client, 'kra_push', False)),
            'kra_push_at': getattr(client, 'kra_push_at', None),
        }
        return _finish_kra_sftp_retry(
            request,
            clientcode,
            retry_result,
            status.HTTP_200_OK,
        )

    already_pushed = reject_if_already_pushed(client, 'kra_push', 'KRA')
    if already_pushed:
        return already_pushed
    _set_kra_push_state(client, False)
    request_payload = None
    response_payload = None
    fetch_request_url = ''
    fetch_response_url = ''
    current_api_name = 'GetToken'
    current_source_api = 'CVL KRA GetToken'
    current_api_url = ''
    last_error_code = ''

    def save_fetch_error(error):
        """Persist a fetch failure when the request was saved before sending."""
        nonlocal fetch_response_url
        if fetch_request_url and not fetch_response_url:
            fetch_response_url = _save_artifact(
                request,
                clientcode,
                'fetch_response',
                _json_text({
                    'success': False,
                    'error': _text(error),
                }),
            )

    artifact_urls = {
        'kra_fetch_request_url': fetch_request_url,
        'kra_fetch_response_url': fetch_response_url,
    }

    def save_audit(kind, content, response_key=None):
        url = _save_artifact(request, clientcode, kind, content)
        artifact_urls[response_key or f'kra_{kind}_url'] = url
        return url

    def safe_headers(headers):
        audited = dict(headers)
        if 'Token' in audited:
            audited['Token'] = '[REDACTED]'
        if 'api_key' in audited:
            audited['api_key'] = '[REDACTED]'
        return audited

    def save_provider_response(kind, api_name, api_url, http_response, provider_response):
        return save_audit(
            kind,
            _json_text({
                'api_name': api_name,
                'api_url': api_url,
                'http_status': getattr(http_response, 'status_code', None),
                'raw_response': getattr(http_response, 'text', ''),
                'response': provider_response,
            }),
        )

    def save_current_error_audit(error):
        """Keep a stage response artifact even when the HTTP call raises."""
        if current_api_name != 'GetPanStatus':
            return
        is_status_check = 'status verification' in current_source_api.lower()
        kind = 'pan_status_check_response' if is_status_check else 'pan_status_response'
        key = f'kra_{kind}_url'
        if key not in artifact_urls:
            save_audit(
                kind,
                _json_text({
                    'api_name': current_api_name,
                    'api_url': current_api_url,
                    'success': False,
                    'error': _text(error),
                }),
            )

    def finish_flow_error(exc, http_status, log_message, error_message=None, log_exception=False):
        """Finalize one of the common KRA flow failures."""
        save_current_error_audit(exc)
        _set_kra_push_state(client, False)
        if log_exception:
            logger.exception(log_message, clientcode)
        else:
            logger.warning(log_message, clientcode, exc)
        save_fetch_error(exc)
        if error_message is None:
            error_response = {
                'success': False,
                'msg': str(exc),
                'errors': [str(exc)],
            }
        else:
            error_response = {
                'success': False,
                'error': str(exc),
                'message': error_message,
                'errors': [str(exc)],
            }
        return _finish(
            request,
            clientcode,
            error_response,
            request_payload,
            _kra_error_artifact(error_response, response_payload),
            http_status,
            artifact_urls,
            api_name=current_api_name,
            source_api=current_source_api,
            api_url=current_api_url,
            error_code=_provider_error(response_payload) or last_error_code,
        )

    try:
        credential = KraCredentials.objects.filter(user=company, environment=environment).first()
        logger.info(
            'KRA credentials lookup completed: clientcode=%s environment=%s configured=%s',
            clientcode,
            environment,
            credential is not None,
        )
        kra_defaults = _fetch_kra_defaults()

        # Build the insert payload before any provider call. This keeps the
        # exact KRA request visible even when token/PAN/fetch calls fail.
        request_payload = _build_insert_payload(
            client,
            credential,
            'CVLKRA',
            '01',
            {},
            kra_defaults,
        )
        logger.info('KRA request payload prepared: clientcode=%s', clientcode)

        if credential is None:
            raise KraError(f'KRA {environment} credentials are not configured.')
        urls = _validate_credential(credential)
        logger.info(
            'KRA credentials validated: clientcode=%s environment=%s',
            clientcode,
            environment,
        )
        headers = {'api_key': _text(credential.api_key), 'user-agent': KRA_USER_AGENT}
        current_api_name = 'GetToken'
        current_source_api = 'CVL KRA GetToken'
        current_api_url = urls['token_url']
        token_result, _, token_http = _post_encrypted(
            urls['token_url'], credential.aes_key,
            {'username': _text(credential.username), 'poscode': _text(credential.poscode), 'password': _text(credential.cvlkra_password)},
            headers,
        )
        response_payload = token_result
        token = _text(token_result.get('token') or token_result.get('Token')) if isinstance(token_result, dict) else ''
        logger.info(
            'KRA GetToken completed: clientcode=%s status=%s token_received=%s',
            clientcode,
            token_http.status_code,
            bool(token),
        )
        if not token_http.ok or not token:
            error = _provider_message(token_result)
            raise KraError(error or 'KRA token generation failed.')

        current_api_name = 'GetPanStatus'
        current_source_api = 'CVL KRA GetPanStatus'
        current_api_url = urls['pan_status_url']
        pan_payload = _build_pan_status_payload(client, credential)
        pan_headers = {'Token': token, 'user-agent': KRA_USER_AGENT}
        pan_encrypted_payload = _encrypt_string(credential.aes_key, pan_payload)
        save_audit('pan_status_header', _json_text(safe_headers({**pan_headers, 'content-type': 'application/json'})))
        save_audit('pan_status_payload', _json_text(pan_payload))
        save_audit('pan_status_payload_enc', _json_text(pan_encrypted_payload))
        pan_result, _, pan_http = _post_encrypted(
            urls['pan_status_url'], credential.aes_key,
            pan_payload,
            pan_headers,
            encrypted_payload=pan_encrypted_payload,
        )
        save_provider_response(
            'pan_status_response',
            current_api_name,
            current_api_url,
            pan_http,
            pan_result,
        )
        response_payload = pan_result
        last_error_code = _provider_error(pan_result)
        _, inquiry = _status_payload(pan_result)
        logger.info(
            'KRA GetPanStatus completed: clientcode=%s status=%s app_status=%s '
            'update_status=%s error_code=%s',
            clientcode,
            pan_http.status_code,
            _text(inquiry.get('APP_STATUS')),
            _text(inquiry.get('APP_UPDT_STATUS')),
            last_error_code or '',
        )
        if not pan_http.ok or _has_provider_error(pan_result):
            error = _provider_message(pan_result)
            raise KraError(error or 'KRA PAN status request failed.')
        app_status = _text(inquiry.get('APP_STATUS'))
        if not app_status:
            raise KraError(_provider_message(pan_result) or 'KRA PAN status did not contain APP_STATUS.')
        update_flag, kra_type = _select_kra(
            app_status,
            inquiry.get('APP_UPDT_STATUS'),
            inquiry.get('APP_MODDT'),
        )
        logger.info(
            'KRA provider mapping selected: clientcode=%s app_status=%s update_flag=%s kra_type=%s',
            clientcode,
            app_status,
            update_flag,
            kra_type,
        )

        fetched = {}
        if update_flag != '01':
            current_api_name = 'SolicitPANDetailsFetchALLKRA'
            current_source_api = 'CVL KRA SolicitPANDetailsFetchALLKRA'
            current_api_url = urls['fetch_data_url']
            fetch_payload = _build_fetch_payload(client, credential, kra_type)
            fetch_encrypted_payload = _encrypt_string(credential.aes_key, fetch_payload)
            fetch_request_url = _save_artifact(
                request,
                clientcode,
                'fetch_request',
                _json_text({
                    'api_name': 'SolicitPANDetailsFetchALLKRA',
                    'api_url': urls['fetch_data_url'],
                    'payload': fetch_payload,
                    'encrypted_payload': fetch_encrypted_payload,
                }),
            )
            artifact_urls['kra_fetch_request_url'] = fetch_request_url

            fetch_headers = {'Token': token, 'user-agent': KRA_USER_AGENT}
            logger.info(
                'KRA fetch started: clientcode=%s kra_type=%s',
                clientcode,
                kra_type,
            )
            fetch_result, _, fetch_http = _post_encrypted(
                urls['fetch_data_url'], credential.aes_key,
                fetch_payload,
                fetch_headers,
                encrypted_payload=fetch_encrypted_payload,
            )
            fetch_response_url = _save_artifact(
                request,
                clientcode,
                'fetch_response',
                _json_text({
                    'api_name': 'SolicitPANDetailsFetchALLKRA',
                    'api_url': urls['fetch_data_url'],
                    'http_status': fetch_http.status_code,
                    'response': fetch_result,
                }),
            )
            artifact_urls['kra_fetch_response_url'] = fetch_response_url
            response_payload = fetch_result
            last_error_code = _provider_error(fetch_result)
            fetched_container = _dictify(fetch_result.get('resdtls', fetch_result)) if isinstance(fetch_result, dict) else {}
            logger.info(
                'KRA fetch completed: clientcode=%s status=%s error_code=%s data_found=%s',
                clientcode,
                fetch_http.status_code,
                last_error_code or '',
                bool(fetched_container.get('KYC_DATA')),
            )
            if not fetch_http.ok or _has_provider_error(fetch_result):
                error = _provider_message(fetch_result)
                raise KraError(error or 'KRA data fetch failed.')
            kyc_data = fetched_container.get('KYC_DATA', {})
            fetched = _dictify(kyc_data[0] if isinstance(kyc_data, list) and kyc_data else kyc_data)
            if not fetched or not _text(fetched.get('APP_NAME')):
                fetch_error = _text(
                    fetched.get('APP_ERROR_DESC')
                    or fetched.get('APP_REMARKS')
                ) or _provider_message(fetch_result)
                raise KraError(
                    fetch_error or 'KRA data not available or DOB is not correct.'
                )

        request_payload = _build_insert_payload(client, credential, kra_type, update_flag, fetched, kra_defaults)
        current_api_name = 'InsertUpdateKYCRecord'
        current_source_api = 'CVL KRA InsertUpdateKYCRecord'
        current_api_url = urls['insert_data_url']
        insert_headers = {'Token': token, 'user-agent': KRA_USER_AGENT}
        insert_encrypted_payload = _encrypt_string(credential.aes_key, request_payload)
        logger.info(
            'KRA InsertUpdateKYCRecord started: clientcode=%s update_flag=%s kra_type=%s',
            clientcode,
            update_flag,
            kra_type,
        )
        save_audit(
            'insert_header',
            _json_text(safe_headers({**insert_headers, 'content-type': 'application/json'})),
        )
        save_audit('insert_payload_enc', _json_text(insert_encrypted_payload))
        insert_result, _, insert_http = _post_encrypted(
            urls['insert_data_url'], credential.aes_key,
            request_payload,
            insert_headers,
            encrypted_payload=insert_encrypted_payload,
        )
        response_payload = insert_result
        last_error_code = _provider_error(insert_result)
        logger.info(
            'KRA InsertUpdateKYCRecord completed: clientcode=%s status=%s error_code=%s',
            clientcode,
            insert_http.status_code,
            last_error_code or '',
        )
        if not isinstance(insert_result, dict):
            raise KraError('KRA insert API returned an invalid response.')

        insert_error_code = _provider_error(insert_result)
        insert_error_message = _provider_message(insert_result)
        if (
            insert_error_code == 'WEBERR-015'
            or 'ACCESS LIMIT EXCEEDED' in insert_error_message.upper()
        ):
            raise KraError(
                'The KRA service request limit has been reached. Please contact '
                'CVL KRA support to request an increase to the access limit.'
            )
        if _has_provider_error(insert_result):
            raise KraError(insert_error_message or 'KRA data error.')

        result_container = _dictify(insert_result.get('resdtls', insert_result))
        ky_data = _dictify(result_container.get('KYCDATA', result_container))
        provider_status = _text(ky_data.get('APP_STATUS'))
        if not provider_status:
            raise KraError(insert_error_message or 'Failed to parse KRA response.')

        message = _text(ky_data.get('APP_STATUS_DESC')) or insert_error_message
        if provider_status not in {'00', '01'}:
            raise KraError(
                message or f'KRA rejected the record with APP_STATUS {provider_status}.'
            )
        success = insert_http.ok and provider_status == '01'

        # CVL can return APP_STATUS=00 while the record is being finalized.
        # The legacy integration checks PAN status again and accepts the push
        # only when APP_UPDT_STATUS ends in 1 and APP_MODDT is today's date.
        status_check_result = None
        if insert_http.ok and provider_status == '00' and not _has_provider_error(insert_result):
            current_api_name = 'GetPanStatus'
            current_source_api = 'CVL KRA GetPanStatus (status verification)'
            current_api_url = urls['pan_status_url']
            status_check_payload = _build_pan_status_payload(client, credential)
            status_check_headers = {'Token': token, 'user-agent': KRA_USER_AGENT}
            status_check_encrypted_payload = _encrypt_string(
                credential.aes_key,
                status_check_payload,
            )
            save_audit(
                'pan_status_check_header',
                _json_text(safe_headers({**status_check_headers, 'content-type': 'application/json'})),
            )
            save_audit('pan_status_check_payload', _json_text(status_check_payload))
            save_audit(
                'pan_status_check_payload_enc',
                _json_text(status_check_encrypted_payload),
            )
            status_check_result, _, status_check_http = _post_encrypted(
                urls['pan_status_url'], credential.aes_key,
                status_check_payload,
                status_check_headers,
                encrypted_payload=status_check_encrypted_payload,
            )
            save_provider_response(
                'pan_status_check_response',
                current_api_name,
                current_api_url,
                status_check_http,
                status_check_result,
            )
            last_error_code = _provider_error(status_check_result)
            logger.info(
                'KRA status verification completed: clientcode=%s status=%s success=%s error_code=%s',
                clientcode,
                status_check_http.status_code,
                not _has_provider_error(status_check_result),
                last_error_code or '',
            )
            response_payload = {
                'insert_response': insert_result,
                'status_check_response': status_check_result,
            }
            _, status_check_inquiry = _status_payload(status_check_result)
            success = (
                status_check_http.ok
                and not _has_provider_error(status_check_result)
                and _kra_status_was_updated_today(status_check_inquiry)
            )
            if success:
                message = 'KRA KYC record accepted after status verification.'
            else:
                message = (
                    _provider_message(status_check_result)
                    or message
                    or 'KRA KYC record is still pending verification.'
                )
        if not message:
            message = 'KRA KYC record accepted.' if success else 'KRA KYC record was rejected.'
        sftp_response = None
        if success:
            logger.info('KRA API data accepted; starting SFTP upload: clientcode=%s', clientcode)
            # Mark the API as accepted before opening SFTP.  If the upload
            # fails, the next request can safely retry only the documents.
            _set_kra_sftp_response(client, KRA_SFTP_PENDING_MARKER)
            try:
                sftp_response = _upload_kra_documents(client, credential)
            except KraSftpError as exc:
                _set_kra_sftp_response(client, f'{KRA_SFTP_ERROR_PREFIX}{exc}')
                raise
            _set_kra_sftp_response(client, sftp_response.get('status', 'UPLOADED'))
            logger.info(
                'KRA SFTP upload completed: clientcode=%s status=%s uploaded_count=%s',
                clientcode,
                sftp_response.get('status'),
                len(sftp_response.get('uploaded', [])),
            )
            response_payload = {
                'provider_response': insert_result,
                'document_upload': sftp_response,
            }
            if status_check_result is not None:
                response_payload['status_check_response'] = status_check_result
            if sftp_response.get('attempted'):
                message = 'KRA KYC record and documents accepted.'
        logger.info('KRA response: clientcode=%s status=%s provider_status=%s', clientcode, insert_http.status_code, provider_status)
        _set_kra_push_state(client, success)
        result = {
            'success': success,
            'message': message,
            'kra_type': kra_type,
            'app_status': app_status,
            'app_update_flag': update_flag,
            'kra_response': insert_result,
            'kra_sftp_response': _kra_sftp_public_response(client),
            'sftp_response': _kra_sftp_public_response(client),
            'kra_push': bool(getattr(client, 'kra_push', False)),
            'kra_push_at': getattr(client, 'kra_push_at', None),
        }
        if not success:
            result.update({
                'error': message,
                'msg': message,
                'errors': [message],
            })
        if sftp_response is not None:
            result['document_upload'] = sftp_response
        return _finish(
            request,
            clientcode,
            result,
            request_payload,
            response_payload,
            status.HTTP_200_OK if success else status.HTTP_502_BAD_GATEWAY,
            artifact_urls,
            api_name=current_api_name,
            source_api=current_source_api,
            api_url=current_api_url,
            error_code=last_error_code,
        )
    except KraSftpError as exc:
        _set_kra_push_state(client, False)
        _set_kra_sftp_response(client, f'{KRA_SFTP_ERROR_PREFIX}{exc}')
        logger.warning('KRA SFTP error: clientcode=%s error=%s', clientcode, exc)
        error_response = {
            'success': False,
            'status': 'KRA_SFTP_ERROR',
            'sftp_retry': True,
            'kra_api_succeeded': True,
            'msg': str(exc),
            'errors': [str(exc)],
            'kra_sftp_response': _kra_sftp_public_response(client),
            'sftp_response': str(exc)[:255],
            'kra_push': bool(getattr(client, 'kra_push', False)),
            'kra_push_at': getattr(client, 'kra_push_at', None),
        }
        return _finish(
            request,
            clientcode,
            error_response,
            request_payload,
            _kra_error_artifact(error_response, response_payload),
            status.HTTP_502_BAD_GATEWAY,
            artifact_urls,
            api_name='KRA SFTP upload',
            source_api='CVL KRA SFTP document upload',
            api_url='',
        )
    except KraError as exc:
        return finish_flow_error(
            exc,
            status.HTTP_400_BAD_REQUEST,
            'KRA validation/provider error: clientcode=%s error=%s',
        )
    except requests.RequestException as exc:
        return finish_flow_error(
            exc,
            status.HTTP_502_BAD_GATEWAY,
            'KRA provider connection failed: clientcode=%s',
            error_message=f'Unable to connect to KRA service: {exc}',
            log_exception=True,
        )
    except (OSError, ValueError, TypeError) as exc:
        return finish_flow_error(
            exc,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            'KRA file or payload operation failed: clientcode=%s',
            error_message=f'KRA file or payload operation failed: {exc}',
            log_exception=True,
        )
    except Exception as exc:
        return finish_flow_error(
            exc,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            'Unexpected KRA integration failure: clientcode=%s',
            error_message=f'Unexpected KRA integration failure: {exc}',
            log_exception=True,
        )
