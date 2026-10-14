"""CKYC flat-file push integration for the Django dashboard.

The actual CKYC push/response handlers can use the same credentials row added
here. This module keeps credential storage isolated by company and environment,
matching the other provider modules.
"""

import datetime as dt
import json
import logging
import re
import zipfile
from urllib.parse import quote

import requests
from django.conf import settings
from django.db import DatabaseError
from django.http import FileResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Ckyc,
    CkycCredentials,
    CkycStateCodeMaster,
    UserDetails,
)
from .push_tracking import (
    reject_if_already_pushed,
    reject_if_api_not_selected,
    reject_if_provider_order_blocked,
)
from .views import _requested_company_user

logger = logging.getLogger(__name__)


def _set_ckyc_push_state(client, state):
    """Store only the successful CKYC time; keep ckyc_push as permission."""
    if not state:
        return
    try:
        client.ckyc_push_at = timezone.localtime()
        client.save(update_fields=['ckyc_push_at'])
    except DatabaseError:
        logger.exception('Unable to save CKYC push state: clientcode=%s', client.clientcode)

CKYC_CLIENT_CODE_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{1,80}$')

# Fields exposed by the CKYC Push credential tab/API.
CKYC_CREDENTIAL_FIELDS = (
    'username',
    'password',
    'ckyc_base_url',
    'auth_api_key',
    'ficode_ckyc',
    'region_or_branch_code_ckyc',
    'userid_ckyc',
    'KYCVerificationName',
    'KYCVerificationDesignation',
    'KYCVerificationBranch',
    'KYCVerificationEMPcode',
    'OrganisationName',
    'OrganisationCode',
)


CKYC_DEFAULT_FIELDS = (
    'record_type', 'record_version', 'detail_record_type', 'detail_version',
    'detail_flag', 'application_type', 'kyc_branch', 'name_update_flag',
    'personal_detail_flag', 'address_update_flag', 'contact_update_flag',
    'record_status', 'ipv_flag', 'identity_type', 'reference_type',
    'name_title', 'father_title', 'mother_title', 'nationality', 'pan_status',
    'pan_exempt_flag', 'correspondence_country', 'correspondence_proof',
    'permanent_address_flag', 'permanent_country', 'permanent_proof',
    'mobile_isd', 'application_date', 'kyc_mode', 'verification_name',
    'verification_designation', 'verification_branch', 'verification_employee_code',
    'organisation_name', 'organisation_code', 'entity_type',
    'footer_record_count', 'footer_fatca_record_count', 'footer_additional_record_count',
)


def _text(value):
    return '' if value is None else str(value).strip()


def _credential_payload(credential):
    return {
        field: _text(getattr(credential, field, ''))
        for field in CKYC_CREDENTIAL_FIELDS
    }


@api_view(['GET', 'POST'])
def ckyc_credentials_view(request):
    """Read or save CKYC credentials for the selected company."""

    company_user = _requested_company_user(request)
    if company_user is None:
        return Response(
            {'error': 'Company not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    environment = _text(
        request.query_params.get('environment')
        if request.method == 'GET'
        else request.data.get('environment')
    ).casefold() or 'uat'

    if environment not in {'uat', 'live'}:
        return Response(
            {'error': 'Environment must be uat or live.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    credential = CkycCredentials.objects.filter(
        user=company_user,
        environment=environment,
    ).first()

    if request.method == 'GET':
        values = _credential_payload(credential) if credential else {
            field: ''
            for field in CKYC_CREDENTIAL_FIELDS
        }
        values['environment'] = environment
        logger.debug(
            'CKYC credentials loaded: company_user_id=%s environment=%s configured=%s',
            company_user.id,
            environment,
            bool(credential),
        )
        return Response({
            'user_id': company_user.id,
            'company': company_user.username,
            'credentials': values,
        })

    values = {
        field: _text(request.data.get(field, ''))
        for field in CKYC_CREDENTIAL_FIELDS
    }
    values['environment'] = environment

    if credential and not values['password']:
        values.pop('password')

    required_fields = (
        'ckyc_base_url',
        'auth_api_key',
        'username',
        'ficode_ckyc',
        'region_or_branch_code_ckyc',
        'userid_ckyc',
    )
    if not credential:
        required_fields = (*required_fields, 'password')

    missing = [field for field in required_fields if not values.get(field)]
    if missing:
        return Response(
            {'error': f'Missing CKYC credential fields: {", ".join(missing)}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    credential, _ = CkycCredentials.objects.update_or_create(
        user=company_user,
        environment=environment,
        defaults=values,
    )
    logger.info(
        'CKYC credentials saved: company_user_id=%s environment=%s',
        company_user.id,
        environment,
    )
    response_values = _credential_payload(credential)
    response_values['environment'] = credential.environment
    return Response({
        'success': True,
        'id': credential.id,
        'user_id': company_user.id,
        'company': company_user.username,
        'credentials': response_values,
    })

def _client_value(client, field, default=''):
    return _text(getattr(client, field, default))


def _safe_clientcode(value):
    """Allow only a client-code format that is safe for artifact paths."""
    value = _text(value)
    return value if CKYC_CLIENT_CODE_PATTERN.fullmatch(value) else ''


def _fetch_ckyc_defaults():
    '''Load editable static CKYC values from the ckyc table.'''
    try:
        defaults = Ckyc.objects.order_by('id').values(*CKYC_DEFAULT_FIELDS).first() or {}
        logger.debug(
            'CKYC defaults loaded: configured_fields=%s',
            [field for field in CKYC_DEFAULT_FIELDS if _text(defaults.get(field))],
        )
        return defaults
    except DatabaseError:
        logger.exception('Unable to load CKYC defaults from ckyc table')
        return {}


def _date(value):
    raw = _text(value)
    match = re.search(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', raw)
    candidate = match.group() if match else raw.split(' ', 1)[0]
    for date_format in (
        '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d',
        '%d%m%Y', '%Y%m%d', '%m/%d/%Y',
    ):
        try:
            return dt.datetime.strptime(candidate, date_format).strftime('%d-%m-%Y')
        except ValueError:
            continue
    return ''


def _split_name(value):
    parts = re.sub(r'[^A-Za-z0-9 ]+', ' ', _text(value)).split()
    if len(parts) == 1:
        return parts[0], '', ''
    if len(parts) == 2:
        return parts[0], '', parts[1]
    return parts[0], ' '.join(parts[1:-1]), parts[-1]


def _split_address(value, width=35):
    words = re.sub(r'[^A-Za-z0-9 ]+', ' ', _text(value)).split()
    lines, current = [], ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return (lines + ['', '', ''])[:3]


def _state_code(value):
    raw_text = _text(value)
    raw = raw_text.casefold()
    if not raw:
        return ''
    try:
        database_code = CkycStateCodeMaster.objects.filter(
            state_name__iexact=raw_text,
        ).values_list('state_code', flat=True).first()
    except DatabaseError:
        logger.exception('Unable to load CKYC state code from ckyc_state_code_master')
        database_code = ''
    if database_code:
        return _text(database_code).upper()
    # Keep already supplied provider codes usable while still preferring the
    # editable master table for state names.
    if re.fullmatch(r'[A-Za-z]{2,3}', raw_text):
        return raw_text.upper()
    logger.warning('CKYC state code not found in master: state=%s', raw_text)
    return ''


def _gender(value):
    raw = _text(value).casefold()
    if raw.startswith('m'):
        return 'Mr', 'M'
    if raw.startswith('f'):
        return 'Mrs', 'F'
    return '', 'O'


def _build_ckyc_lines(client, credential, options, defaults=None):
    first, middle, last = _split_name(
        _client_value(client, 'aadhaar_name') or _client_value(client, 'pan')
    )
    father_first, father_middle, father_last = _split_name(
        _client_value(client, 'fathername')
    )
    mother_first, mother_middle, mother_last = _split_name(
        _client_value(client, 'mothername')
    )
    defaults = defaults or {}
    static = lambda field, fallback='': _text(defaults.get(field)) or fallback
    prefix, gender = _gender(_client_value(client, 'aadhaar_gender'))
    address = ' '.join(filter(None, (
        _client_value(client, 'aadhaar_address'),
        _client_value(client, 'addressline1'),
        _client_value(client, 'addressline2'),
        _client_value(client, 'addressline3'),
    )))
    address1, address2, address3 = _split_address(address)
    state = _state_code(_client_value(client, 'aadhaar_state'))
    today = timezone.localdate().strftime('%d-%m-%Y')
    ckyc_number = _text(options.get('ckycno'))
    calculated_application_type = '03' if len(ckyc_number) == 14 else '01'
    application_type = '03' if calculated_application_type == '03' else static('application_type', '01')
    reference = ckyc_number if application_type == '03' else static('reference_type', '1')

    def flag(option_name, field_name):
        option_value = _text(options.get(option_name))
        if option_value:
            return '01' if option_value.casefold() in {'1', 'true', 'yes', 'y'} else '02'
        return static(field_name, '02')

    proof_of_address = _text(options.get('proof_of_address')) or static('correspondence_proof', '01')
    permanent_proof = _text(options.get('permanent_proof')) or static('permanent_proof', proof_of_address)
    father_spouse_flag = _text(options.get('father_spouse_flag')) or '01'
    differently_abled_status = _text(options.get('differently_abled_status_flag')) or '0'
    impairment_type = _text(options.get('type_of_impairment'))
    impairment_percentage = _text(options.get('percentage_of_impairment'))
    udid_number = _text(options.get('udid_number'))
    date_of_declaration = static('application_date', today)
    place_of_declaration = _client_value(client, 'aadhaar_dist')
    verification_date = _text(options.get('verification_date'))

    # CKYC record 20 is positional. Keep this layout identical to the
    # provider specification/legacy generator; changing the order shifts all
    # following values into the wrong tags.
    fields = [
        static('detail_record_type', '20'), static('detail_version', '1'), application_type,
        static('kyc_branch', _text(getattr(credential, 'KYCVerificationBranch', ''))),
        flag('name_flag', 'name_update_flag'), flag('personal_flag', 'personal_detail_flag'),
        flag('address_flag', 'address_update_flag'), flag('contact_flag', 'contact_update_flag'),
        static('remarks_update_flag', static('record_status', '02')), flag('ipv_flag', 'ipv_flag'),
        static('identity_type', '01'), static('related_person_flag', '02'), '',
        static('image_update_flag', '01' if application_type == '03' else '02'),
        '01', '01', '', '01', reference,
        prefix, first, middle, last,
        '', '', '', '', '', '',
        father_spouse_flag, static('father_title', 'Mr'), father_first, father_middle, father_last, '',
        static('mother_title', 'Mrs'), mother_first, mother_middle, mother_last, '',
        gender, _text(options.get('marital_status')), static('nationality', '01'),
        _client_value(client, 'occupation'), _date(_client_value(client, 'aadhaar_dob')),
        '', '', '', '', '', '', '',
        _client_value(client, 'pan').upper(), static('pan_status', '01'),
        differently_abled_status, impairment_type, impairment_percentage, udid_number,
        '', '', address1, address2, address3,
        _client_value(client, 'aadhaar_dist'), _client_value(client, 'aadhaar_dist'), state,
        static('correspondence_country', _client_value(client, 'aadhaar_country') or 'IN'),
        _client_value(client, 'aadhaar_pincode'), static('correspondence_proof', '01'),
        proof_of_address,
        static('permanent_address_flag', 'Y'), '', address1, address2, address3,
        _client_value(client, 'aadhaar_dist'), _client_value(client, 'aadhaar_dist'), state,
        static('permanent_country', _client_value(client, 'aadhaar_country') or 'IN'),
        _client_value(client, 'aadhaar_pincode'), permanent_proof, '',
        '', '', '', '', '', '', '', '', '', '',
        '', '', '',
        static('mobile_isd', '91'), re.sub(r'\D', '', _client_value(client, 'mobile'))[:10],
        '', '', _client_value(client, 'email'), '', date_of_declaration,
        place_of_declaration, verification_date, static('kyc_mode', '02'),
        static('verification_name', _text(getattr(credential, 'KYCVerificationName', ''))),
        static('verification_designation', _text(getattr(credential, 'KYCVerificationDesignation', ''))),
        static('verification_branch', _text(getattr(credential, 'KYCVerificationBranch', ''))),
        static('verification_employee_code', _text(getattr(credential, 'KYCVerificationEMPcode', ''))),
        static('organisation_name', _text(getattr(credential, 'OrganisationName', ''))),
        static('organisation_code', _text(getattr(credential, 'OrganisationCode', ''))),
        '1', '00', '0', '', '00', '', '', '', '', '', '',
    ]
    detail_line = f"30|{static('detail_version', '1')}|{static('detail_flag', 'E')}|{_client_value(client, 'aadhaar_no')}||||02|||||"
    return ['|'.join(fields), detail_line]


def _storage_dir(clientcode):
    clientcode = _safe_clientcode(clientcode)
    if not clientcode:
        raise ValueError('Invalid client code.')
    directory = settings.BASE_DIR / 'static' / 'ckyc_data' / clientcode
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _save_ckyc_artifact(request, clientcode, kind, body):
    clientcode = _safe_clientcode(clientcode)
    if not clientcode:
        raise ValueError('Invalid client code.')
    directory = _storage_dir(clientcode)
    path = directory / f'ckyc_{kind}.txt'
    temporary_path = path.with_name(f'.{path.name}.tmp')
    temporary_path.write_text(_text(body), encoding='utf-8')
    temporary_path.replace(path)
    return request.build_absolute_uri(
        f'/api/ckyc_file/{quote(clientcode, safe="")}/{kind}/'
    )


def _safe_response(response):
    try:
        return response.json()
    except ValueError:
        return {'status_code': response.status_code, 'raw_response': response.text}


def _push_error(
    request,
    clientcode,
    message,
    http_status=400,
    client=None,
    request_payload=None,
    request_url='',
    archive_url='',
    log_url='',
):
    error_message = _text(message)
    body = {
        'success': False,
        'error': error_message,
        'message': error_message,
        'msg': error_message,
        'errors': [error_message],
    }
    response_body = dict(body)
    if client is not None:
        _set_ckyc_push_state(client, False)
    try:
        body['ckyc_response_url'] = _save_ckyc_artifact(
            request, clientcode, 'response',
            json.dumps(response_body, indent=2, ensure_ascii=False),
        )
    except (OSError, ValueError):
        logger.exception('Unable to save CKYC push error: clientcode=%s', clientcode)
    if request_payload is not None:
        body['request_payload'] = request_payload
    if request_url:
        body['ckyc_request_url'] = request_url
    if archive_url:
        body['ckyc_archive_url'] = archive_url
    if log_url:
        body['ckyc_log_url'] = log_url
    body['ckyc_response'] = response_body
    return Response(body, status=http_status)


def _credential_is_ready(credential):
    return credential and all(_text(getattr(credential, field, '')) for field in (
        'ckyc_base_url', 'auth_api_key', 'username', 'password',
        'ficode_ckyc', 'region_or_branch_code_ckyc', 'userid_ckyc',
    ))


def _ckyc_upload_url(credential, environment):
    base_url = _text(credential.ckyc_base_url).rstrip('/')
    return f'{base_url}/sftp/{environment}/upload'


def _write_ckyc_archive(directory, prefix, content):
    """Create the provider archive atomically, so partial ZIPs are never used."""
    archive_path = directory / f'{prefix}.zip'
    temporary_path = directory / f'.{prefix}.zip.tmp'
    with zipfile.ZipFile(temporary_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f'{prefix}.txt', content)
    temporary_path.replace(archive_path)
    return archive_path


@api_view(['POST'])
def ckyc_ucc_modify(request, clientcode):
    """Generate and optionally submit the CKYC file for one UserDetails row."""

    clientcode = _safe_clientcode(clientcode)
    if not clientcode:
        return Response(
            {'success': False, 'message': 'Invalid client code.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info('CKYC push started: clientcode=%s', clientcode)
    company = _requested_company_user(request)
    if company is None:
        return Response({'success': False, 'message': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)

    client = UserDetails.objects.filter(clientcode=clientcode, user=company).first()
    if client is None:
        return Response({'success': False, 'message': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
    api_not_selected = reject_if_api_not_selected(client, 'CKYC')
    if api_not_selected:
        return api_not_selected
    already_pushed = reject_if_already_pushed(client, 'ckyc_push', 'CKYC')
    if already_pushed:
        return already_pushed
    order_blocked = reject_if_provider_order_blocked(client, 'CKYC')
    if order_blocked:
        return order_blocked
    _set_ckyc_push_state(client, False)

    environment = _text(
        request.data.get('environment') or request.query_params.get('environment') or 'uat'
    ).casefold()
    credential = (
        CkycCredentials.objects.filter(user=company, environment=environment).first()
        if environment in {'uat', 'live'}
        else None
    )

    content = None
    request_url = ''
    archive_url = ''
    log_url = ''
    try:
        defaults = _fetch_ckyc_defaults()
        lines = _build_ckyc_lines(client, credential or {}, request.data, defaults)
        date_number = timezone.localdate().strftime('%d%m%Y')
        series = timezone.localtime().strftime('%H%M%S')
        ficode = _text(getattr(credential, 'ficode_ckyc', ''))
        branch_code = _text(getattr(credential, 'region_or_branch_code_ckyc', ''))
        userid = _text(getattr(credential, 'userid_ckyc', ''))
        prefix = f'{ficode}_{branch_code}_{date_number}_V1.3_{userid}_U{series}'
        header = f"{_text(defaults.get('record_type')) or '10'}|{series}|{ficode}|{branch_code}|1|{timezone.localdate().strftime('%d-%m-%Y')}|{_text(defaults.get('record_version')) or 'V1.3'}|01||||"
        content = header + '\n' + '\n'.join(lines) + '\n'

        directory = _storage_dir(clientcode)
        request_path = directory / 'ckyc_request.txt'
        temporary_request_path = request_path.with_name(f'.{request_path.name}.tmp')
        temporary_request_path.write_text(content, encoding='utf-8')
        temporary_request_path.replace(request_path)
        zip_path = _write_ckyc_archive(directory, prefix, content)
        trigger_path = directory / f'{prefix}.trg'
        trigger_path.write_bytes(b'')
        request_url = request.build_absolute_uri(f'/api/ckyc_file/{quote(clientcode, safe="")}/request/')
        archive_url = request.build_absolute_uri(f'/api/ckyc_file/{quote(clientcode, safe="")}/archive/')
        log_url = request.build_absolute_uri(f'/api/ckyc_file/{quote(clientcode, safe="")}/push_log/')

        if environment not in {'uat', 'live'}:
            return _push_error(
                request,
                clientcode,
                'Environment must be uat or live.',
                client=client,
                request_payload=content,
                request_url=request_url,
                archive_url=archive_url,
                log_url=log_url,
            )

        if not _credential_is_ready(credential):
            return _push_error(
                request,
                clientcode,
                f'CKYC {environment} credentials are not configured completely.',
                client=client,
                request_payload=content,
                request_url=request_url,
                archive_url=archive_url,
                log_url=log_url,
            )

        with zip_path.open('rb') as zip_file, trigger_path.open('rb') as trigger_file:
            response = requests.post(
                _ckyc_upload_url(credential, environment),
                headers={'x-auth-token': _text(credential.auth_api_key)},
                data={'username': _text(credential.username), 'password': _text(credential.password)},
                files={
                    'zip': (zip_path.name, zip_file, 'application/zip'),
                    'trigger': (trigger_path.name, trigger_file, 'application/octet-stream'),
                },
                timeout=120,
                verify=getattr(settings, 'CKYC_VERIFY_SSL', True),
            )
        result = _safe_response(response)
        response_url = _save_ckyc_artifact(
            request, clientcode, 'response',
            json.dumps(result, indent=2, ensure_ascii=False, default=str),
        )
        logger.info('CKYC provider response: clientcode=%s status=%s', clientcode, response.status_code)
        _set_ckyc_push_state(client, response.ok)
        return Response({
            'success': response.ok,
            'message': result.get('status') if isinstance(result, dict) else 'CKYC provider response received.',
            'ckyc_request_url': request_url,
            'ckyc_archive_url': archive_url,
            'ckyc_response_url': response_url,
            'ckyc_log_url': log_url,
            'ckyc_response': result,
            'filename': zip_path.name,
        }, status=status.HTTP_200_OK if response.ok else status.HTTP_502_BAD_GATEWAY)
    except requests.RequestException as exc:
        _set_ckyc_push_state(client, False)
        logger.exception('CKYC provider connection failed: clientcode=%s', clientcode)
        error_message = f'Unable to connect to CKYC service: {exc}'
        error = {
            'success': False,
            'msg': error_message,
            'errors': [error_message],
        }
        response_url = _save_ckyc_artifact(request, clientcode, 'response', json.dumps(error, indent=2))
        return Response({
            **error,
            'request_payload': content,
            'ckyc_request_url': request_url,
            'ckyc_archive_url': archive_url,
            'ckyc_log_url': log_url,
            'ckyc_response_url': response_url,
            'ckyc_response': error,
        }, status=status.HTTP_502_BAD_GATEWAY)
    except (OSError, ValueError) as exc:
        _set_ckyc_push_state(client, False)
        logger.exception('CKYC file generation failed: clientcode=%s', clientcode)
        error_message = f'CKYC file generation failed: {exc}'
        error = {
            'success': False,
            'msg': error_message,
            'errors': [error_message],
        }
        try:
            error['ckyc_response_url'] = _save_ckyc_artifact(
                request, clientcode, 'response', json.dumps(error, indent=2)
            )
        except OSError:
            logger.exception('Unable to save CKYC generation error: clientcode=%s', clientcode)
        return Response({
            **error,
            'request_payload': content,
            'ckyc_request_url': request_url,
            'ckyc_archive_url': archive_url,
            'ckyc_log_url': log_url,
            'ckyc_response': error,
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
def ckyc_file(request, clientcode, kind):
    clientcode = _safe_clientcode(clientcode)
    if not clientcode:
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    if kind not in {
        'request', 'response', 'archive', 'push_log',
    }:
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    company = _requested_company_user(request)
    if company is None or (
        not request.user.is_staff
        and not UserDetails.objects.filter(clientcode=clientcode, user=request.user).exists()
    ):
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)

    directory = _storage_dir(clientcode)
    if kind == 'archive':
        archives = sorted(directory.glob('*.zip'), key=lambda item: item.stat().st_mtime, reverse=True)
        path = archives[0] if archives else None
    else:
        file_kind = 'response' if kind == 'push_log' else kind
        path = directory / f'ckyc_{file_kind}.txt'
    if path is None or not path.is_file():
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    return FileResponse(
        path.open('rb'),
        as_attachment=True,
        filename=path.name,
        content_type='application/zip' if kind == 'archive' else 'text/plain',
    )
