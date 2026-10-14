"""MSE India UCC integration for the Django dashboard.

MSE accepts a JSON UCC upload asynchronously.  The upload returns a request
number, so the request is checked again until MSE reports that it is processed.
The client is marked pushed only after the processed response contains no
client-level errors.
"""

import datetime as dt
import json
import logging
import re
from pathlib import Path
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
    MseAccountTypeMaster,
    MseCredentials,
    MseIncomeRangeMaster,
    MseOccupationMaster,
    MseStateCodeMaster,
    UserDetails,
)
from .push_tracking import reject_if_already_pushed, reject_if_api_not_selected
from .views import _requested_company_user


logger = logging.getLogger(__name__)

MSE_BASE_URLS = {
    'uat': 'https://uatucc.msei.in/uccservice/api',
    'live': 'https://ucc.mseindia.com/uccservice/api',
}
MSE_CLIENT_CODE_PATTERN = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}\Z')
MSE_ARTIFACT_KINDS = {'request', 'response', 'status'}

MSE_STATE_CODES = {
    'ANDAMAN & NICOBAR ISLANDS': '1', 'ANDAMAN AND NICOBAR ISLANDS': '1',
    'ANDHRA PRADESH': '2', 'AP': '2', 'ARUNACHAL PRADESH': '3', 'AR': '3',
    'ASSAM': '4', 'AS': '4', 'BIHAR': '5', 'BR': '5', 'CHANDIGARH': '6', 'CH': '6',
    'DADRA & NAGAR HAVELI': '7', 'DADRA AND NAGAR HAVELI': '7', 'DN': '7',
    'DAMAN & DIU': '8', 'DAMAN AND DIU': '8', 'DD': '8', 'DELHI': '9', 'DL': '9',
    'NEW DELHI': '9', 'GOA': '10', 'GA': '10', 'GUJARAT': '11', 'GJ': '11',
    'HARYANA': '12', 'HR': '12', 'HIMACHAL PRADESH': '13', 'HP': '13',
    'JAMMU & KASHMIR': '14', 'JAMMU AND KASHMIR': '14', 'JK': '14',
    'KARNATAKA': '15', 'KA': '15', 'KERALA': '16', 'KL': '16',
    'LAKSHADWEEP': '17', 'LD': '17', 'MADHYA PRADESH': '18', 'MP': '18',
    'MAHARASHTRA': '19', 'MH': '19', 'MANIPUR': '20', 'MN': '20',
    'MEGHALAYA': '21', 'ML': '21', 'MIZORAM': '22', 'MZ': '22',
    'NAGALAND': '23', 'NL': '23', 'ORISSA': '24', 'ODISHA': '24', 'OR': '24', 'OD': '24',
    'PONDICHERRY': '25', 'PUDUCHERRY': '25', 'PY': '25', 'PUNJAB': '26', 'PB': '26',
    'RAJASTHAN': '27', 'RJ': '27', 'SIKKIM': '28', 'SK': '28',
    'TAMIL NADU': '29', 'TN': '29', 'TRIPURA': '30', 'TR': '30',
    'UTTAR PRADESH': '31', 'UP': '31', 'WEST BENGAL': '32', 'WB': '32',
    'CHHATTISGARH': '33', 'CG': '33', 'UTTARAKHAND': '34', 'UK': '34',
    'UTTARANCHAL': '34', 'JHARKHAND': '35', 'JH': '35', 'TELANGANA': '37', 'TS': '37',
    'LADAKH': '38', 'LA': '38', 'OTHERS': '99',
}
MSE_OCCUPATION_CODES = {
    'PUBLIC SECTOR': '1', 'PRIVATE SECTOR': '2', 'GOVERNMENT SERVICE': '3',
    'BUSINESS': '4', 'PROFESSIONAL': '5', 'AGRICULTURIST': '6', 'RETIRED': '7',
    'HOUSEWIFE': '8', 'STUDENT': '9', 'OTHER': '99', 'OTHERS': '99',
}
MSE_INCOME_CODES = {
    'BELOW 1 LAC': '1', '1-5 LAC': '2', '5-10 LAC': '3', '10-25 LAC': '4',
    'MORE THAN 25 LAC': '5', '25-1 CRORE': '5', 'ABOVE 25 LAC': '5', '> 1 CRORE': '6',
    '25-50 LACS': '5', '50 LACS-1 CRORE': '5', 'ABOVE 1 CRORE': '6',
}
MSE_ACCOUNT_TYPE_CODES = {
    'SAVING ACCOUNT': '10', 'SAVINGS ACCOUNT': '10', 'SAVING': '10',
    'CURRENT ACCOUNT': '11', 'CURRENT': '11', 'OTHERS': '99', 'OTHER': '99',
}


class MseError(Exception):
    """Safe MSE error returned to the frontend."""

    def __init__(self, message, provider_response=None):
        super().__init__(message)
        self.provider_response = provider_response


def _text(value):
    return '' if value is None else str(value).strip()


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _safe_clientcode(value):
    value = _text(value)
    return value if MSE_CLIENT_CODE_PATTERN.fullmatch(value) else re.sub(r'[^A-Za-z0-9_.-]', '_', value)[:80]


def _storage_dir(clientcode):
    directory = Path(settings.BASE_DIR) / 'static' / 'mse_data' / _safe_clientcode(clientcode)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _artifact_url(request, clientcode, kind):
    return request.build_absolute_uri(
        f'/api/mse_file/{quote(_safe_clientcode(clientcode), safe="")}/{kind}/'
    )


def _save_artifact(request, clientcode, kind, content):
    path = _storage_dir(clientcode) / f'mse_{kind}.txt'
    temporary = path.with_name(f'.{path.name}.tmp')
    temporary.write_text(
        content if isinstance(content, str) else _json_text(content),
        encoding='utf-8',
    )
    temporary.replace(path)
    logger.info('MSE artifact saved: clientcode=%s kind=%s bytes=%s', clientcode, kind, path.stat().st_size)
    return _artifact_url(request, clientcode, kind)


def _credential_payload(credential):
    return {
        'environment': credential.environment if credential else 'uat',
        'login_id': credential.login_id if credential else '',
        'password': credential.password if credential else '',
    }


def _base_url(credential):
    environment = _text(getattr(credential, 'environment', '')).lower() or 'uat'
    if environment not in MSE_BASE_URLS:
        raise MseError('MSE environment must be uat or live.')
    return MSE_BASE_URLS[environment]


def _date_ddmmyyyy(value):
    raw = _text(value)
    if not raw:
        return ''
    for pattern in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d', '%d%m%Y'):
        try:
            return dt.datetime.strptime(raw.split(' ', 1)[0], pattern).strftime('%d%m%Y')
        except ValueError:
            continue
    return ''


def _state_code(value):
    raw = _text(value)
    if not raw:
        return ''
    return _master_code(
        MseStateCodeMaster,
        'state_name',
        'state_code',
        raw,
        MSE_STATE_CODES,
        '99',
    )


def _master_code(model, label_field, code_field, value, fallback_map=None, fallback=''):
    raw = _text(value).upper()
    if not raw:
        return fallback
    try:
        code = model.objects.filter(
            **{f'{label_field}__iexact': raw},
        ).values_list(code_field, flat=True).first()
        if not code:
            code = model.objects.filter(
                **{f'{code_field}__iexact': raw},
            ).values_list(code_field, flat=True).first()
        if code:
            logger.debug(
                'MSE master value mapped: table=%s field=%s value=%s',
                model._meta.db_table,
                label_field,
                raw,
            )
            return _text(code)
    except DatabaseError:
        logger.exception('MSE master lookup failed: table=%s field=%s', model._meta.db_table, label_field)

    normalized = re.sub(r'[^A-Z0-9]+', ' ', raw).strip()
    if fallback_map:
        for label, code in fallback_map.items():
            if re.sub(r'[^A-Z0-9]+', ' ', label).strip() == normalized:
                logger.warning(
                    'MSE master value not found; using compatibility fallback: table=%s value=%s',
                    model._meta.db_table,
                    raw,
                )
                return code
    logger.warning(
        'MSE master value not found: table=%s field=%s value=%s',
        model._meta.db_table,
        label_field,
        raw,
    )
    return fallback


def _mapped_code(value, mapping, fallback='', model=None, label_field='', code_field=''):
    if model:
        return _master_code(model, label_field, code_field, value, mapping, fallback)
    raw = _text(value).upper()
    return mapping.get(raw, fallback)


def _flag(value, default='N'):
    return 'Y' if _text(value).casefold() in {'1', 'true', 'yes', 'y', 'on'} else default


def _digits(value):
    return re.sub(r'[^0-9]', '', _text(value))


def _client_getter(client):
    values = {
        field.name.lower(): getattr(client, field.name, '')
        for field in client._meta.concrete_fields
    }

    def get(*names):
        for name in names:
            value = _text(values.get(name.lower()))
            if value:
                return value
        return ''

    return get


def _build_mse_payload(client):
    get = _client_getter(client)
    client_name = get('aadhaar_name')
    address = get('aadhaar_address') or ' '.join(
        filter(None, (get('addressline1'), get('addressline2'), get('addressline3')))
    )
    address = re.sub(r'[^A-Za-z0-9 ]+', '', address).strip()
    city = get('aadhaar_dist')
    state = _state_code(get('aadhaar_state'))
    pincode = get('aadhaar_pincode')
    dob = _date_ddmmyyyy(get('aadhaar_dob'))
    mobile = _digits(get('mobile'))
    aadhaar = _digits(get('aadhaar_no'))
    if len(aadhaar) != 12:
        aadhaar = ''
    gender_value = get('aadhaar_gender').upper()
    gender = 'M' if gender_value in {'M', 'MALE'} else 'F' if gender_value in {'F', 'FEMALE'} else 'T' if gender_value else ''
    account_type = _mapped_code(
        get('accounttype'),
        MSE_ACCOUNT_TYPE_CODES,
        '10',
        model=MseAccountTypeMaster,
        label_field='account_type',
        code_field='account_code',
    )
    depository = get('dptype').upper()
    if depository not in {'CDSL', 'NSDL'}:
        depository = ''
    dpid = get('dpid').upper()
    depository_id = dpid[:8] if len(dpid) >= 8 else dpid
    beneficiary_account = dpid[8:] if len(dpid) > 8 else ''
    bank_account_type = account_type
    agreement_date = timezone.localdate().strftime('%d%m%Y')

    payload = {f'ccdReserved{number}': '' for number in range(1, 62)}
    payload.update({
        'ccdECM': _flag(get('bse_cash')),
        'ccdEDS': _flag(get('bse_fo')),
        'ccdCDS': _flag(get('bse_currency')),
        'ccdClientCode': get('clientcode'),
        'ccdClientName': client_name,
        'ccdAccountType': 'CLIENT',
        'ccdCategory': '1',
        'ccdPANNo': get('pan').upper(),
        'ccdGender': gender,
        'ccdGuardianName': get('fathername'),
        'ccdNationality': '1',
        'ccdEmailID': get('email'),
        'ccdRelationshipWithClientForEmail': '1',
        'ccdCorrespondenceClientAddress': address,
        'ccdCorrespondenceClientCity': city,
        'ccdCorrespondenceClientState': state,
        'ccdCorrespondenceClientOtherState': '',
        'ccdCorrespondenceClientCountry': '85',
        'ccdCorrespondenceClientPinCode': pincode,
        'ccdPermanentAddSameAsCorrs': 'Y',
        'ccdPermanentAddress': address,
        'ccdPermanentCity': city,
        'ccdPermanentState': state,
        'ccdPermanentOtherState': '',
        'ccdPermanentCountryCode': '85',
        'ccdPermanentPincode': pincode,
        'ccdMobileNo': mobile,
        'ccdRelationshipWithClientForMobile': '1',
        'ccdOfficeTelephoneNo': '',
        'ccdISDCode': '',
        'ccdSTDCode': '',
        'ccdDateofBirth': dob,
        'ccdUID': aadhaar,
        'ccdBankName1': get('bankname'),
        'ccdIFSCCode1': get('ifsc').upper(),
        'ccdBankAccountNo1': get('bankaccountnumber'),
        'ccdBankAccountType1': bank_account_type,
        'ccdPrimarySecondaryBank1': 'P',
        'ccdCINOfClient': '',
        'ccdGrossAnnualIncomeRange': _mapped_code(
            get('annual_income'),
            MSE_INCOME_CODES,
            '0',
            model=MseIncomeRangeMaster,
            label_field='income_range',
            code_field='income_code',
        ),
        'ccdGrossAnnualIncomeDate': _date_ddmmyyyy(get('annual_income_date')),
        'ccdNetworth': '' if get('networth') in {'0', '0.0'} else get('networth'),
        'ccdNetworthAsOnDate': _date_ddmmyyyy(get('networth_date')),
        'ccdPEPersopn': '0',
        'ccdOccupation': _mapped_code(
            get('occupation'),
            MSE_OCCUPATION_CODES,
            '99',
            model=MseOccupationMaster,
            label_field='occupation_name',
            code_field='occupation_code',
        ),
        'ccdOccupationDetails': '',
        'ccdCPCodeECM': '', 'ccdCPCodeEDS': '', 'ccdCPCodeCDS': '',
        'ccdRegistrationNo': '', 'ccdRegisteringAuthority': '',
        'ccdRegistrationPlace': '', 'ccdRegistrationDate': '',
        'ccdInpersonVerification': '',
        'ccdAgreementDate': agreement_date,
        'ccdTypeOfFacility': '3',
        'ccdUpdationFlagSMSEmail': '',
        'ccdRelationshipCode': '',
        'ccdProofType': '', 'ccdProofNo': '', 'ccdPlaceOfProof': '', 'ccdIssueProofDate': '',
        'ccdStatus': 'A',
        'ccdClientTypeCorporate': 'N',
        'ccdPOAFunds': _flag(get('isdppoa')),
        'ccdPOASecurities': _flag(get('isdppoa')),
        'ccdPOAFundsDate': '', 'ccdPOASecuritiesDate': '',
        'ccdDDPISettlement': 'N', 'ccdDDPISettlementDate': '',
        'ccdDDPIPledging': 'N', 'ccdDDPIPledgingDate': '',
        'ccdNominationOption': '1' if _flag(get('nominee_check')) == 'Y' else '2',
        'ccdUPIOpt': '',
        'ccdClientNameDescription': client_name,
        'ccdFlag': 'E',
    })

    for number in range(2, 11):
        payload.update({
            f'ccdBankName{number}': '', f'ccdIFSCCode{number}': '',
            f'ccdBankAccountNo{number}': '', f'ccdBankAccountType{number}': '',
            f'ccdPrimarySecondaryBank{number}': '',
        })
    for number in range(1, 6):
        payload.update({
            f'ccdDepositoryName{number}': '', f'ccdDepositoryId{number}': '',
            f'ccdBeneficiaryAccountNo{number}': '', f'ccdPrimarySecondaryDP{number}': '',
        })
    if depository:
        payload.update({
            'ccdDepositoryName1': depository,
            'ccdDepositoryId1': depository_id,
            'ccdBeneficiaryAccountNo1': beneficiary_account,
            'ccdPrimarySecondaryDP1': 'P',
        })
    for prefix in ('ECM', 'EDS', 'CDS'):
        payload.update({
            f'ccd{prefix}CPName': '', f'ccd{prefix}CPPANNo': '',
            f'ccd{prefix}CPEmailId': '', f'ccd{prefix}CorrespondenceCPAddress': '',
            f'ccd{prefix}CorrespondenceCPCity': '', f'ccd{prefix}CorrespondenceCPState': '',
            f'ccd{prefix}CorrespondenceCPOtherState': '',
            f'ccd{prefix}CorrespondenceCPCountry': '',
            f'ccd{prefix}CorrespondenceCPPinCode': '', f'ccd{prefix}CPMobileNo': '',
            f'ccd{prefix}CPISDCode': '', f'ccd{prefix}CPSTDCode': '',
            f'ccd{prefix}CPTelephoneNo': '',
        })
    for number in range(1, 7):
        payload.update({
            f'ccdCPName{number}': '', f'ccdCPDesignation{number}': '',
            f'ccdCPPANNo{number}': '', f'ccdCPAddress{number}': '',
            f'ccdCPContactDetails{number}': '', f'ccdCPDIN{number}': '',
            f'ccdCPEmailID{number}': '',
        })
    logger.info('MSE payload prepared: clientcode=%s fields=%s', get('clientcode'), len(payload))
    return payload


def _response_json(response, stage):
    try:
        data = response.json()
    except ValueError as exc:
        raise MseError(
            f'MSE {stage} returned a non-JSON response (HTTP {response.status_code}).',
            response.text[:2000],
        ) from exc
    if not isinstance(data, dict):
        raise MseError(
            f'MSE {stage} returned an invalid JSON object (HTTP {response.status_code}).',
            data,
        )
    return data


def _authenticate(credential):
    login_id = _text(getattr(credential, 'login_id', ''))
    password = _text(getattr(credential, 'password', ''))
    if not login_id or not password:
        raise MseError('MSE credentials are not configured completely: login_id and password are required.')
    url = f'{_base_url(credential)}/auth'
    logger.info('MSE authentication started: environment=%s login_id=%s', credential.environment, login_id)
    try:
        response = requests.post(
            url,
            json={'loginId': login_id, 'password': password, 'apiName': 'ucc_auth'},
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise MseError(f'Unable to connect to MSE authentication service: {exc}') from exc
    data = _response_json(response, 'authentication')
    if not response.ok or _text(data.get('status')) != '1' or not _text(data.get('token')):
        error_code = _text(data.get('errorcode') or data.get('errorCode')) or 'Unknown'
        raise MseError(f'MSE authentication failed. Error code: {error_code}.', data)
    return _text(data['token']), data


def _upload(credential, token, payload):
    login_id = _text(credential.login_id)
    url = f'{_base_url(credential)}/clientupload'
    headers = {
        'Content-Type': 'application/json',
        'authorization': token,
        'apiName': 'Ucc_clientupload',
        'loginId': login_id,
    }
    request_body = {'request': [payload]}
    logger.info('MSE UCC upload started: login_id=%s', login_id)
    try:
        response = requests.post(url, json=request_body, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise MseError(f'Unable to connect to MSE upload service: {exc}') from exc
    data = _response_json(response, 'upload')
    request_no = _text(data.get('requestNo'))
    if not response.ok or not request_no:
        error_code = _text(data.get('errorCode') or data.get('errorcode')) or 'Unknown'
        raise MseError(f'MSE upload failed. Error code: {error_code}.', data)
    logger.info('MSE UCC upload accepted: request_no=%s', request_no)
    return request_no, data


def _status(credential, token, request_no):
    login_id = _text(credential.login_id)
    url = f'{_base_url(credential)}/clientupload/status'
    try:
        response = requests.get(
            url,
            json={'requestNo': request_no},
            headers={
                'Content-Type': 'application/json',
                'authorization': token,
                'apiName': 'Ucc_clientupload',
                'loginId': login_id,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise MseError(f'Unable to connect to MSE status service: {exc}') from exc
    data = _response_json(response, 'status')
    if not response.ok:
        error_code = _text(data.get('errorCode') or data.get('errorcode')) or f'HTTP {response.status_code}'
        raise MseError(f'MSE status check failed. Error code: {error_code}.', data)
    provider_status = _text(data.get('status'))
    if provider_status == '2':
        return 'processed', data
    if provider_status == '1':
        return 'in_process', data
    if provider_status == '-1':
        raise MseError('MSE rejected the request number as invalid.', data)
    error_code = _text(data.get('errorCode') or data.get('errorcode'))
    raise MseError(
        f'MSE status check failed{f": Error code: {error_code}" if error_code else "."}',
        data,
    )


def _processed_result(data):
    errors = []
    responses = data.get('response', []) if isinstance(data, dict) else []
    if not isinstance(responses, list):
        responses = []
    for item in responses:
        if not isinstance(item, dict) or _text(item.get('responseStatus')) != '2':
            continue
        client_code = _text(item.get('clientCode'))
        provider_errors = [
            f'{label}: {item[field]}'
            for field, label in (
                ('ecmErrorCode', 'ECM Error'),
                ('edsErrorCode', 'EDS Error'),
                ('cdsErrorCode', 'CDS Error'),
            )
            if _text(item.get(field))
        ]
        errors.append(f'Client {client_code}: {", ".join(provider_errors) or "MSE rejected the client."}')
    return errors


def _set_request_state(client, request_no=None, in_process=None, provider_status=None):
    updates = []
    if request_no is not None:
        client.mse_request_no = _text(request_no)
        updates.append('mse_request_no')
    if in_process is not None:
        client.mse_in_process = bool(in_process)
        updates.append('mse_in_process')
    if provider_status is not None:
        client.mse_status = _text(provider_status)
        updates.append('mse_status')
    if updates:
        client.save(update_fields=updates)


def _set_mse_push_state(client, success):
    if not success:
        return
    client.mse_push = True
    client.mse_push_at = timezone.localtime()
    client.mse_in_process = False
    client.mse_status = 'Processed'
    client.save(update_fields=['mse_push', 'mse_push_at', 'mse_in_process', 'mse_status'])
    logger.info('MSE push state saved: clientcode=%s', client.clientcode)


def _finish(request, clientcode, result, request_payload, response_payload, http_status):
    result = dict(result)
    result['request_payload'] = request_payload
    result['mse_response'] = response_payload
    result['mse_request_url'] = _save_artifact(request, clientcode, 'request', request_payload)
    result['mse_response_url'] = _save_artifact(request, clientcode, 'response', response_payload)
    if isinstance(response_payload, dict) and response_payload.get('status_response') is not None:
        result['mse_status_url'] = _save_artifact(
            request, clientcode, 'status', response_payload['status_response'],
        )
    return Response(result, status=http_status)


@api_view(['GET', 'POST'])
def mse_credentials_view(request):
    company = _requested_company_user(request)
    if company is None:
        return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    credential = MseCredentials.objects.filter(user=company).first()
    if request.method == 'GET':
        return Response({
            'user_id': company.id,
            'company': company.username,
            'credentials': _credential_payload(credential),
        })

    values = {
        'environment': _text(request.data.get('environment') or 'uat').lower(),
        'login_id': _text(request.data.get('login_id')),
        'password': _text(request.data.get('password')),
    }
    if values['environment'] not in MSE_BASE_URLS:
        return Response({'error': 'Environment must be uat or live.'}, status=status.HTTP_400_BAD_REQUEST)
    if credential and not values['password']:
        values.pop('password')
    if not values['login_id'] and not (credential and credential.login_id):
        return Response({'error': 'MSE login ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not values.get('password') and not (credential and credential.password):
        return Response({'error': 'MSE password is required.'}, status=status.HTTP_400_BAD_REQUEST)
    saved, _ = MseCredentials.objects.update_or_create(user=company, defaults=values)
    logger.info('MSE credentials saved: company_user_id=%s environment=%s', company.id, saved.environment)
    return Response({
        'success': True,
        'user_id': company.id,
        'company': company.username,
        'credentials': _credential_payload(saved),
    })


@api_view(['GET'])
def mse_file(request, clientcode, kind):
    if kind not in MSE_ARTIFACT_KINDS or not MSE_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    company = _requested_company_user(request)
    if company is None:
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not (request.user.is_staff or request.user.is_superuser) and not UserDetails.objects.filter(clientcode=clientcode, user=request.user).exists():
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    path = _storage_dir(clientcode) / f'mse_{kind}.txt'
    if not path.is_file():
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    return FileResponse(path.open('rb'), as_attachment=True, filename=path.name, content_type='text/plain')


@api_view(['POST'])
def mse_ucc_modify(request, clientcode):
    clientcode = _text(clientcode)
    logger.info('MSE UCC request started: clientcode=%s', clientcode)
    if not MSE_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({'success': False, 'msg': 'Invalid client code.'}, status=status.HTTP_400_BAD_REQUEST)
    company = _requested_company_user(request)
    if company is None:
        return Response({'success': False, 'msg': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    client = UserDetails.objects.filter(clientcode=clientcode, user=company).first()
    if client is None:
        return Response({'success': False, 'msg': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
    api_not_selected = reject_if_api_not_selected(client, 'MSE')
    if api_not_selected:
        return api_not_selected
    already_pushed = reject_if_already_pushed(client, 'mse_push', 'MSE')
    if already_pushed:
        return already_pushed

    request_payload = {'request': [_build_mse_payload(client)]}
    response_payload = {}
    try:
        credential = MseCredentials.objects.filter(user=company).first()
        if credential is None:
            raise MseError('MSE credentials are not configured.')

        token, auth_response = _authenticate(credential)
        request_no = _text(getattr(client, 'mse_request_no', ''))
        if request_no and getattr(client, 'mse_in_process', False):
            logger.info('MSE status retry started: clientcode=%s request_no=%s', clientcode, request_no)
            state, status_response = _status(credential, token, request_no)
            response_payload = {'authentication': auth_response, 'status_response': status_response}
        else:
            request_no, upload_response = _upload(credential, token, request_payload['request'][0])
            _set_request_state(client, request_no, True, 'In Process')
            state, status_response = _status(credential, token, request_no)
            response_payload = {
                'authentication': auth_response,
                'upload_response': upload_response,
                'status_response': status_response,
            }

        if state == 'in_process':
            _set_request_state(client, request_no, True, 'In Process')
            return _finish(
                request, clientcode,
                {
                    'success': False,
                    'status': 'MSE_PROCESSING',
                    'msg': f'MSE UCC upload accepted. Request No: {request_no}. Please check again later.',
                    'request_no': request_no,
                    'in_process': True,
                },
                request_payload, response_payload, status.HTTP_202_ACCEPTED,
            )

        errors = _processed_result(status_response)
        if errors:
            _set_request_state(client, request_no, False, 'Failed')
            message = '; '.join(errors)
            return _finish(
                request, clientcode,
                {
                    'success': False,
                    'status': 'MSE_PROCESSING_ERROR',
                    'msg': message,
                    'errors': errors,
                    'request_no': request_no,
                },
                request_payload, response_payload, status.HTTP_502_BAD_GATEWAY,
            )

        _set_request_state(client, request_no, False, 'Processed')
        _set_mse_push_state(client, True)
        return _finish(
            request, clientcode,
            {
                'success': True,
                'status': 'MSE_PROCESSED',
                'msg': f'MSE UCC processed successfully. Request No: {request_no}.',
                'request_no': request_no,
            },
            request_payload, response_payload, status.HTTP_200_OK,
        )
    except MseError as exc:
        logger.warning('MSE request failed: clientcode=%s error=%s', clientcode, exc)
        response_payload = {
            'success': False,
            'error': str(exc),
            'provider_response': exc.provider_response,
        }
        return _finish(
            request, clientcode,
            {
                'success': False,
                'status': 'MSE_ERROR',
                'msg': str(exc),
                'errors': [str(exc)],
            },
            request_payload, response_payload, status.HTTP_502_BAD_GATEWAY,
        )
    except (DatabaseError, OSError, TypeError, ValueError) as exc:
        logger.exception('MSE database, file, or payload error: clientcode=%s', clientcode)
        response_payload = {'success': False, 'error': str(exc)}
        return _finish(
            request, clientcode,
            {
                'success': False,
                'status': 'MSE_LOCAL_ERROR',
                'msg': str(exc),
                'errors': [str(exc)],
            },
            request_payload, response_payload, status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:
        logger.exception('Unexpected MSE integration error: clientcode=%s', clientcode)
        response_payload = {'success': False, 'error': str(exc)}
        return _finish(
            request, clientcode,
            {
                'success': False,
                'status': 'MSE_UNEXPECTED_ERROR',
                'msg': str(exc),
                'errors': [str(exc)],
            },
            request_payload, response_payload, status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
