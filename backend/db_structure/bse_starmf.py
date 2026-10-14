"""BSE Star MF UCC integration.

The provider accepts a JSON envelope whose ``Param`` value is a fixed
pipe-delimited record. User values come from ``UserDetails`` and all
provider defaults come from the editable ``BseStarMf`` master row.
"""

import datetime as dt
import json
import logging
import re
from collections.abc import Mapping
from urllib.parse import quote

import requests
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    BseStarMf,
    BseStarMfCredentials,
    BseStarMfDependencyMaster,
    BseStarMfGenderMaster,
    BseStarMfStateCodeMaster,
    BseStarMfTaxStatusMaster,
    UserDetails,
)
from .push_tracking import (
    reject_if_already_pushed,
    reject_if_api_not_selected,
    reject_if_provider_order_blocked,
)
from .views import _requested_company_user

logger = logging.getLogger(__name__)

BSE_STAR_MF_URLS = {
    'uat': 'https://bsestarmfdemo.bseindia.com/BSEMFWEBAPI/UCCAPI/UCCRegistration',
    'live': 'https://www.bsestarmf.in/BSEMFWEBAPI/UCCAPI/UCCRegistration',
}
BSE_STAR_MF_CLIENT_CODE_PATTERN = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}')
BSE_STAR_MF_DATE_FORMATS = (
    '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y',
)

NEW_TAIL_FIELDS = (
    'primary_holder_kyc_type', 'primary_holder_ckyc_number',
    'second_holder_kyc_type', 'second_holder_ckyc_number',
    'third_holder_kyc_type', 'third_holder_ckyc_number',
    'guardian_holder_kyc_type', 'guardian_holder_ckyc_number',
    'primary_holder_kra_exempt_ref_number',
    'second_holder_kra_exempt_ref_number',
    'third_holder_kra_exempt_ref_number',
    'guardian_holder_kra_exempt_ref_number',
    'aadhar_seeding_status', 'mapin_id', 'paperless_flag', 'lei_no',
    'lei_validity', 'mobile_declaration_flag', 'email_declaration_flag',
    'second_holder_email', 'second_holder_email_declaration',
    'second_holder_mobile', 'second_holder_mobile_declaration',
    'third_holder_email', 'third_holder_email_declaration',
    'third_holder_mobile', 'third_holder_mobile_declaration',
    'guardian_relationship', 'nominee_opt', 'nominee_auth_mode',
)

MODIFY_TAIL_FIELDS = (
    'primary_holder_kyc_type', 'primary_holder_ckyc_number',
    'second_holder_kyc_type', 'second_holder_ckyc_number',
    'third_holder_kyc_type', 'third_holder_ckyc_number',
    'guardian_holder_kyc_type', 'guardian_holder_ckyc_number',
    'primary_holder_kra_exempt_ref_number',
    'second_holder_kra_exempt_ref_number',
    'third_holder_kra_exempt_ref_number',
    'guardian_holder_kra_exempt_ref_number',
    'aadhar_seeding_status', 'mapin_id', 'paperless_flag', 'lei_no',
    'lei_validity', 'mobile_declaration_flag', 'email_declaration_flag',
    'nominee_opt', 'nominee_auth_mode', 'nominee1_pan', 'nominee1_guard_pan',
    'nominee2_pan', 'nominee2_guard_pan', 'nominee3_pan', 'nominee3_guard_pan',
    'second_holder_email', 'second_holder_email_declaration',
    'second_holder_mobile', 'second_holder_mobile_declaration',
    'third_holder_email', 'third_holder_email_declaration',
    'third_holder_mobile', 'third_holder_mobile_declaration',
    'guardian_relationship',
)


class BseStarMfError(Exception):
    """Expected integration/configuration error."""


def _text(value):
    return '' if value is None else str(value).strip()


def _set_bse_starmf_push_state(client, state):
    """Store only the successful push time; keep permission unchanged."""
    if not state:
        return
    try:
        client.bsestarmf_push_at = timezone.localtime()
        client.save(update_fields=['bsestarmf_push_at'])
    except DatabaseError:
        logger.exception(
            'Unable to save BSE Star MF push state: clientcode=%s',
            client.clientcode,
        )


def _getter(client):
    if isinstance(client, Mapping):
        values = {str(key).lower(): value for key, value in client.items()}
    else:
        values = {
            field.name.lower(): getattr(client, field.name, '')
            for field in client._meta.concrete_fields
        }

    def get(*names):
        for name in names:
            value = _text(values.get(str(name).lower(), ''))
            if value:
                return value
        return ''

    return get


def _parse_date(value):
    raw = _text(value)
    match = re.search(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', raw)
    candidate = match.group() if match else raw.split(' ', 1)[0]
    for date_format in BSE_STAR_MF_DATE_FORMATS:
        try:
            return dt.datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    return None


def _date(value):
    parsed = _parse_date(value)
    return parsed.strftime('%d/%m/%Y') if parsed else ''


def _split_name(value):
    parts = _text(value).split()
    if not parts:
        raise BseStarMfError('Aadhaar name is required for BSE Star MF.')
    if len(parts) == 1:
        return parts[0], '', ''
    if len(parts) == 2:
        return parts[0], parts[1], ''
    return parts[0], ' '.join(parts[1:-1]), parts[-1]


def _clean(value):
    return re.sub(r'[^A-Za-z0-9 .,/\-]', '', _text(value))


def _split_address(value, width=35, count=3):
    words = _clean(value).split()
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return (lines + [''] * count)[:count]


def _lookup_master_code(model, label_field, code_field, value, fallback_label=''):
    """Resolve a provider code from an editable master table."""
    raw = _text(value)
    lookup_label = _text(fallback_label) if not raw else raw
    if not lookup_label:
        return ''

    try:
        code = model.objects.filter(
            **{f'{code_field}__iexact': lookup_label}
        ).values_list(code_field, flat=True).first()
        if code:
            return _text(code)

        code = model.objects.filter(
            **{f'{label_field}__iexact': lookup_label}
        ).values_list(code_field, flat=True).first()
        if code:
            return _text(code)

        normalized = re.sub(r'[^a-z0-9]+', ' ', lookup_label.casefold()).strip()
        if normalized:
            for label, code in model.objects.values_list(label_field, code_field):
                candidate = re.sub(r'[^a-z0-9]+', ' ', _text(label).casefold()).strip()
                if candidate == normalized:
                    return _text(code)
    except DatabaseError:
        logger.exception(
            'Could not read BSE Star MF lookup table: model=%s value=%s',
            model.__name__, lookup_label,
        )
    return ''


def _state_code(value):
    raw = _text(value)
    code = _lookup_master_code(
        BseStarMfStateCodeMaster,
        'state_name',
        'state_code',
        raw,
        fallback_label='others' if not raw else '',
    )
    if code:
        return code
    # Accept a provider code supplied directly by an upstream client.
    return raw.upper() if len(raw) <= 3 else ''


def _gender_code(value):
    raw = _text(value)
    code = _lookup_master_code(
        BseStarMfGenderMaster,
        'gender',
        'gender_code',
        raw,
    )
    if not code:
        # Use the editable "other" row as the table-driven default.
        code = _lookup_master_code(
            BseStarMfGenderMaster,
            'gender',
            'gender_code',
            'other',
        )
    return code or 'O'


def _tax_status(value, default='01'):
    raw = _text(value)
    code = _lookup_master_code(
        BseStarMfTaxStatusMaster,
        'tax_status',
        'tax_code',
        raw,
        fallback_label='individual' if not raw else '',
    )
    if code:
        return code
    # Accept a provider code supplied directly by an upstream client.
    return raw if raw.isdigit() and len(raw) <= 2 else default


def _dependency_flag(value, default='SE'):
    raw = _text(value)
    code = _lookup_master_code(
        BseStarMfDependencyMaster,
        'dependency',
        'dependency_code',
        raw,
        fallback_label='self' if not raw and default == 'SE' else '',
    )
    if code:
        return code
    # Preserve support for a provider code or an explicit custom default.
    return default if not raw else raw.upper()[:2]


def _age(value):
    parsed = _parse_date(value)
    if not parsed:
        return None
    today = timezone.localdate()
    return today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))


def _master_defaults(master):
    return {
        field.name: _text(getattr(master, field.name, ''))
        for field in master._meta.concrete_fields
        if not field.primary_key
    }


def _nominee_values(get, number):
    prefix = f'nominee{number}'
    name = ' '.join(filter(None, (
        get(f'{prefix}_firstname'),
        get(f'{prefix}_middlename'),
        get(f'{prefix}_lastname'),
    )))
    if not name:
        return {
            'name': '', 'relationship': '', 'percent': '', 'minor': '', 'dob': '',
            'guardian': '', 'pan': '', 'guard_pan': '', 'id_type': '', 'id_no': '',
            'email': '', 'mobile': '', 'address1': '', 'address2': '', 'address3': '',
            'city': '', 'pincode': '', 'con': '',
        }
    dob = get(f'{prefix}_dob')
    return {
        'name': name,
        'relationship': get(f'{prefix}_relation')[:40],
        # The current UserDetails schema has no nominee percentage column.
        'percent': '',
        'minor': 'Y' if (_age(dob) is not None and _age(dob) < 18) else 'N',
        'dob': _date(dob) if (_age(dob) is not None and _age(dob) < 18) else '',
        'guardian': '',
        'pan': get(f'{prefix}_pan'),
        'guard_pan': '',
        'id_type': '',
        'id_no': '',
        'email': get(f'{prefix}_email'),
        'mobile': get(f'{prefix}_mobile'),
        'address1': get(f'{prefix}_address1'),
        'address2': get(f'{prefix}_address2'),
        'address3': '',
        'city': get(f'{prefix}_city'),
        'pincode': get(f'{prefix}_pincode'),
        'con': get(f'{prefix}_country'),
    }


def _build_param(client, master):
    get = _getter(client)
    master_config = _master_defaults(master)
    first, middle, last = _split_name(get('aadhaar_name'))
    dob = _date(get('aadhaar_dob'))
    client_code = get('clientcode')
    pan = get('pan').upper()
    if not client_code or not pan:
        raise BseStarMfError('Client code and PAN are required for BSE Star MF.')

    address = ' '.join(filter(None, (
        get('aadhaar_address', 'addressline1'),
        get('addressline2'), get('addressline3'),
    )))
    address1, address2, address3 = _split_address(address)
    dptype = get('dptype').upper()
    dpid = get('dpid')
    cdsl_dpid = cdsl_client_id = nsdl_dpid = nsdl_client_id = ''
    if dptype == 'CDSL' and dpid:
        if not dpid.isdigit() or len(dpid) != 16:
            raise BseStarMfError('CDSL DP ID must contain exactly 16 digits.')
        cdsl_dpid, cdsl_client_id = dpid[:8], dpid[8:]
    elif dptype == 'NSDL' and dpid:
        if len(dpid) != 16:
            raise BseStarMfError('NSDL DP ID must contain exactly 16 characters.')
        nsdl_dpid, nsdl_client_id = dpid[:8], dpid[8:]

    bank_account = get('bankaccountnumber')
    bank_type = get('accounttype')
    bank_name = get('bankname')
    bank_ifsc = get('ifsc').upper()
    bank_micr = get('micr')
    if not bank_account or not bank_name:
        raise BseStarMfError('Bank name and bank account number are required.')

    nominees = [_nominee_values(get, number) for number in (1, 2, 3)]
    nominee_enabled = _text(get('nominee_check')).casefold() in {'yes', 'y', 'true', '1'}
    if not nominee_enabled:
        nominees = [{key: '' for key in nominee} for nominee in nominees]
    else:
        nominees = [nominee for nominee in nominees]
    nominee_enabled = nominee_enabled and any(nominee['name'] for nominee in nominees)

    values = {
        'clientcode': client_code,
        'primary_first_name': first,
        'primary_middle_name': middle,
        'primary_last_name': last,
        'tax_status': _tax_status(master_config.get('tax_status'), '01'),
        'gender': _gender_code(get('aadhaar_gender', 'gender')),
        'dob': dob,
        'occupation': get('occupation'),
        'holding_nature': master_config.get('holding_nature', 'SI'),
        'second_holder_first_name': '', 'second_holder_middle_name': '',
        'second_holder_last_name': '', 'third_holder_first_name': '',
        'third_holder_middle_name': '', 'third_holder_last_name': '',
        'second_holder_dob': '', 'third_holder_dob': '',
        'guardian_first_name': '', 'guardian_middle_name': '',
        'guardian_last_name': '', 'guardian_dob': '',
        'primary_pan_holder_exempt': master_config.get('primary_pan_holder_exempt', 'N'),
        'second_pan_holder_exempt': master_config.get('second_pan_holder_exempt', ''),
        'third_pan_holder_exempt': master_config.get('third_pan_holder_exempt', ''),
        'guardian_pan_holder_exempt': master_config.get('guardian_pan_holder_exempt', ''),
        'pan': pan,
        'second_holder_pan': '', 'third_holder_pan': '', 'guardian_holder_pan': '',
        'primary_pan_holder_exempt_category': master_config.get('primary_pan_holder_exempt_category', ''),
        'second_pan_holder_exempt_category': master_config.get('second_pan_holder_exempt_category', ''),
        'third_pan_holder_exempt_category': master_config.get('third_pan_holder_exempt_category', ''),
        'guardian_pan_holder_exempt_category': master_config.get('guardian_pan_holder_exempt_category', ''),
        'client_type': master_config.get('client_type', 'P'),
        'pms': master_config.get('pms', ''),
        'default_dp': dptype,
        'cdsl_dpid': cdsl_dpid, 'cdsl_client_id': cdsl_client_id,
        'cmbpid': '', 'nsdl_dpid': nsdl_dpid, 'nsdl_client_id': nsdl_client_id,
        'account_type_1': bank_type, 'client_account_no_1': bank_account,
        'micr_no_1': bank_micr, 'ifsc_code_1': bank_ifsc, 'default_bank_flag_1': 'Y',
        'account_type_2': '', 'client_account_no_2': '', 'micr_no_2': '',
        'ifsc_code_2': '', 'default_bank_flag_2': '',
        'account_type_3': '', 'client_account_no_3': '', 'micr_no_3': '',
        'ifsc_code_3': '', 'default_bank_flag_3': '',
        'account_type_4': '', 'client_account_no_4': '', 'micr_no_4': '',
        'ifsc_code_4': '', 'default_bank_flag_4': '',
        'account_type_5': '', 'client_account_no_5': '', 'micr_no_5': '',
        'ifsc_code_5': '', 'default_bank_flag_5': '',
        'client_cheque_name_5': '',
        'div_pay_mode': master_config.get('div_pay_mode', '02'),
        'address1': address1, 'address2': address2, 'address3': address3,
        'city': get('aadhaar_dist'),
        'state': _state_code(get('aadhaar_state')),
        'pincode': get('aadhaar_pincode'),
        'country': get('aadhaar_country') or 'India',
        'residential_phone': '', 'residential_fax': '', 'office_phone': '',
        'office_fax': '', 'email': get('email'),
        'communication_mode': master_config.get('communication_mode', 'E'),
        'foreign_address_1': master_config.get('foreign_address_1', ''),
        'foreign_address_2': master_config.get('foreign_address_2', ''),
        'foreign_address_3': master_config.get('foreign_address_3', ''),
        'foreign_city': master_config.get('foreign_city', ''),
        'foreign_pincode': master_config.get('foreign_pincode', ''),
        'foreign_state': master_config.get('foreign_state', ''),
        'foreign_country': master_config.get('foreign_country', ''),
        'foreign_residential_phone': '', 'foreign_residential_fax': '',
        'foreign_office_phone': '', 'foreign_office_fax': '',
        'indian_mobile': get('mobile'),
        'primary_holder_kyc_type': master_config.get('primary_holder_kyc_type', 'K'),
        'primary_holder_ckyc_number': master_config.get('primary_holder_ckyc_number', ''),
        'second_holder_kyc_type': master_config.get('second_holder_kyc_type', ''),
        'second_holder_ckyc_number': master_config.get('second_holder_ckyc_number', ''),
        'third_holder_kyc_type': master_config.get('third_holder_kyc_type', ''),
        'third_holder_ckyc_number': master_config.get('third_holder_ckyc_number', ''),
        'guardian_holder_kyc_type': master_config.get('guardian_holder_kyc_type', ''),
        'guardian_holder_ckyc_number': master_config.get('guardian_holder_ckyc_number', ''),
        'primary_holder_kra_exempt_ref_number': master_config.get('primary_holder_kra_exempt_ref_number', ''),
        'second_holder_kra_exempt_ref_number': master_config.get('second_holder_kra_exempt_ref_number', ''),
        'third_holder_kra_exempt_ref_number': master_config.get('third_holder_kra_exempt_ref_number', ''),
        'guardian_holder_kra_exempt_ref_number': master_config.get('guardian_holder_kra_exempt_ref_number', ''),
        'aadhar_seeding_status': master_config.get('aadhar_seeding_status', ''),
        'mapin_id': master_config.get('mapin_id', ''), 'paperless_flag': master_config.get('paperless_flag', 'Z'),
        'lei_no': master_config.get('lei_no', ''), 'lei_validity': master_config.get('lei_validity', ''),
        'mobile_declaration_flag': _dependency_flag(master_config.get('mobile_declaration_flag', 'SE')),
        'email_declaration_flag': _dependency_flag(master_config.get('email_declaration_flag', 'SE')),
        'second_holder_email': '', 'second_holder_email_declaration': '',
        'second_holder_mobile': '', 'second_holder_mobile_declaration': '',
        'third_holder_email': '', 'third_holder_email_declaration': '',
        'third_holder_mobile': '', 'third_holder_mobile_declaration': '',
        'guardian_relationship': master_config.get('guardian_relationship', ''),
        'nominee_opt': 'Y' if nominee_enabled else 'N',
        'nominee_auth_mode': master_config.get('nominee_auth_mode', 'O') if nominee_enabled else '',
        'nominee_soa': 'Y' if nominee_enabled else 'N',
    }

    for number, nominee in enumerate(nominees, start=1):
        address_lines = _split_address(
            ' '.join(filter(None, (nominee['address1'], nominee['address2'], nominee['address3']))),
            width=40,
        )
        values.update({
            f'nominee_{number}_name': nominee['name'],
            f'nominee_{number}_relationship': nominee['relationship'],
            f'nominee_{number}_percent': nominee['percent'],
            f'nominee_{number}_minor': nominee['minor'],
            f'nominee_{number}_dob': nominee['dob'],
            f'nominee_{number}_guardian': nominee['guardian'],
            f'nominee_{number}_guard_pan': nominee['guard_pan'],
            f'nominee_{number}_id_type': nominee['id_type'],
            f'nominee_{number}_id_no': nominee['id_no'],
            f'nominee_{number}_email': nominee['email'],
            f'nominee_{number}_mobile': nominee['mobile'],
            f'nominee_{number}_address1': address_lines[0],
            f'nominee_{number}_address2': address_lines[1],
            f'nominee_{number}_address3': address_lines[2],
            f'nominee_{number}_city': nominee['city'],
            f'nominee_{number}_pincode': nominee['pincode'],
            f'nominee_{number}_con': nominee['con'],
            f'nominee{number}_pan': nominee['pan'],
            f'nominee{number}_guard_pan': nominee['guard_pan'],
        })

    base_param = [
        values['clientcode'], values['primary_first_name'], values['primary_middle_name'],
        values['primary_last_name'], values['tax_status'], values['gender'], values['dob'],
        values['occupation'], values['holding_nature'], values['second_holder_first_name'],
        values['second_holder_middle_name'], values['second_holder_last_name'],
        values['third_holder_first_name'], values['third_holder_middle_name'],
        values['third_holder_last_name'], values['second_holder_dob'], values['third_holder_dob'],
        values['guardian_first_name'], values['guardian_middle_name'], values['guardian_last_name'],
        values['guardian_dob'], values['primary_pan_holder_exempt'], values['second_pan_holder_exempt'],
        values['third_pan_holder_exempt'], values['guardian_pan_holder_exempt'], values['pan'],
        values['second_holder_pan'], values['third_holder_pan'], values['guardian_holder_pan'],
        values['primary_pan_holder_exempt_category'], values['second_pan_holder_exempt_category'],
        values['third_pan_holder_exempt_category'], values['guardian_pan_holder_exempt_category'],
        values['client_type'], values['pms'], values['default_dp'], values['cdsl_dpid'],
        values['cdsl_client_id'], values['cmbpid'], values['nsdl_dpid'], values['nsdl_client_id'],
    ]
    for slot in range(1, 6):
        base_param.extend(values[f'{key}_{slot}'] for key in (
            'account_type', 'client_account_no', 'micr_no', 'ifsc_code', 'default_bank_flag',
        ))
    base_param.extend([
        values['client_cheque_name_5'], values['div_pay_mode'], values['address1'], values['address2'],
        values['address3'], values['city'], values['state'], values['pincode'], values['country'],
        values['residential_phone'], values['residential_fax'], values['office_phone'], values['office_fax'],
        values['email'], values['communication_mode'], values['foreign_address_1'], values['foreign_address_2'],
        values['foreign_address_3'], values['foreign_city'], values['foreign_pincode'], values['foreign_state'],
        values['foreign_country'], values['foreign_residential_phone'], values['foreign_residential_fax'],
        values['foreign_office_phone'], values['foreign_office_fax'], values['indian_mobile'],
    ])
    registration_type = _text(master_config.get('registration_type')).upper() or 'NEW'
    if registration_type != 'NEW':
        modify_param = list(base_param)
        for number in (1, 2, 3):
            modify_param.extend(values[f'nominee_{number}_{field}'] for field in (
                'name', 'relationship', 'percent', 'minor', 'dob', 'guardian',
            ))
        modify_param.extend(values[field] for field in MODIFY_TAIL_FIELDS)
        modify_param.extend(['', '', '', ''])
        return '|'.join(_text(value) for value in modify_param) + '|'

    new_param = list(base_param)
    new_param.extend(values[field] for field in NEW_TAIL_FIELDS)
    for number in (1, 2, 3):
        new_param.extend(values[f'nominee_{number}_{field}'] for field in (
            'name', 'relationship', 'percent', 'minor', 'dob', 'guardian', 'guard_pan',
            'id_type', 'id_no', 'email', 'mobile', 'address1', 'address2', 'address3',
            'city', 'pincode', 'con',
        ))
    new_param.extend([values['nominee_soa'], '', '', '', '', '', '', ''])
    return '|'.join(_text(value) for value in new_param) + '|'


def _save_artifact(request, clientcode, kind, body):
    directory = settings.BASE_DIR / 'static' / 'bse_star_mf_data' / clientcode
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'bse_starmf_{kind}.txt'
    temporary = path.with_name(f'.{path.name}.tmp')
    temporary.write_text(body, encoding='utf-8')
    temporary.replace(path)
    logger.info('BSE Star MF artifact saved: clientcode=%s kind=%s bytes=%s', clientcode, kind, len(body.encode('utf-8')))
    return request.build_absolute_uri(f'/api/bse_starmf_file/{quote(clientcode, safe="")}/{kind}/')


def _artifact_url(request, clientcode, kind):
    return request.build_absolute_uri(f'/api/bse_starmf_file/{quote(clientcode, safe="")}/{kind}/')


def _response_json(response):
    try:
        return response.json()
    except ValueError:
        return {
            'success': False,
            'status': 'NON_JSON_RESPONSE',
            'status_code': response.status_code,
            'message': 'BSE Star MF returned a non-JSON response.',
            'raw_response': response.text,
        }


@api_view(['GET', 'POST'])
def bse_starmf_credentials_view(request):
    company = _requested_company_user(request)
    if company is None:
        return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    environment = _text(
        request.query_params.get('environment')
        if request.method == 'GET'
        else request.data.get('environment')
    ).lower() or 'uat'
    if environment not in BSE_STAR_MF_URLS:
        return Response({'error': 'Environment must be uat or live.'}, status=status.HTTP_400_BAD_REQUEST)
    credential = BseStarMfCredentials.objects.filter(user=company, environment=environment).first()
    if request.method == 'GET':
        return Response({
            'user_id': company.id,
            'company': company.username,
            'credentials': {
                'environment': environment,
                'MemberId': credential.MemberId if credential else '',
                'UserId': credential.UserId if credential else '',
                'Password': credential.Password if credential else '',
            },
        })
    values = {
        'environment': environment,
        'MemberId': _text(request.data.get('MemberId', '')),
        'UserId': _text(request.data.get('UserId', '')),
        'Password': _text(request.data.get('Password', '')),
    }
    if credential and not values['Password']:
        values.pop('Password')
    if not values.get('MemberId') or not values.get('UserId') or (not values.get('Password') and credential is None):
        return Response({'error': 'Member ID, User ID and Password are required.'}, status=status.HTTP_400_BAD_REQUEST)
    credential, _ = BseStarMfCredentials.objects.update_or_create(
        user=company,
        environment=environment,
        defaults=values,
    )
    logger.info('BSE Star MF credentials saved: user_id=%s environment=%s', company.id, environment)
    return Response({
        'success': True,
        'user_id': company.id,
        'company': company.username,
        'credentials': {
            'environment': credential.environment,
            'MemberId': credential.MemberId,
            'UserId': credential.UserId,
            'Password': credential.Password,
        },
    })


@api_view(['GET'])
def bse_starmf_file(request, clientcode, kind):
    if kind not in {'request', 'response'} or not BSE_STAR_MF_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    company = _requested_company_user(request)
    if company is None:
        return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not (request.user.is_staff or request.user.is_superuser):
        if not UserDetails.objects.filter(clientcode=clientcode, user=request.user).exists():
            return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    path = settings.BASE_DIR / 'static' / 'bse_star_mf_data' / clientcode / f'bse_starmf_{kind}.txt'
    if not path.is_file():
        return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
    from django.http import FileResponse
    return FileResponse(path.open('rb'), as_attachment=True, filename=path.name, content_type='text/plain')


@api_view(['POST'])
def bse_starmf_ucc_modify(request, clientcode):
    logger.info('BSE Star MF UCC request started: clientcode=%s', clientcode)
    client = None
    if not BSE_STAR_MF_CLIENT_CODE_PATTERN.fullmatch(clientcode):
        return Response({'success': False, 'message': 'Invalid client code.'}, status=status.HTTP_400_BAD_REQUEST)
    company = _requested_company_user(request)
    if company is None:
        return Response({'success': False, 'message': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    client = UserDetails.objects.filter(clientcode=clientcode, user=company).first()
    if client is None:
        return Response({'success': False, 'message': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
    api_not_selected = reject_if_api_not_selected(client, 'BSE STAR MF')
    if api_not_selected:
        return api_not_selected
    already_pushed = reject_if_already_pushed(client, 'bsestarmf_push', 'BSE Star MF')
    if already_pushed:
        return already_pushed
    order_blocked = reject_if_provider_order_blocked(client, 'BSE STAR MF')
    if order_blocked:
        return order_blocked
    _set_bse_starmf_push_state(client, False)
    master = BseStarMf.objects.order_by('id').first()
    if master is None:
        _set_bse_starmf_push_state(client, False)
        return Response({'success': False, 'message': 'BSE Star MF master record not found.'}, status=status.HTTP_400_BAD_REQUEST)
    environment = _text(request.data.get('environment') or request.query_params.get('environment') or 'uat').lower()
    request_url = ''
    request_payload = None
    try:
        credential = (
            BseStarMfCredentials.objects.filter(user=company, environment=environment).first()
            if environment in BSE_STAR_MF_URLS
            else None
        )

        param = _build_param(client, master)
        envelope = {
            'UserId': _text(getattr(credential, 'UserId', '')),
            'MemberCode': _text(getattr(credential, 'MemberId', '')),
            'Password': _text(getattr(credential, 'Password', '')),
            'RegnType': _text(master.registration_type) or 'NEW',
            'Param': param,
            'Filler1': _text(master.filler1),
            'Filler2': _text(master.filler2),
        }
        request_payload = envelope
        request_body = json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))
        artifact_envelope = {**envelope}
        request_url = _save_artifact(
            request,
            clientcode,
            'request',
            json.dumps(artifact_envelope, ensure_ascii=False, separators=(',', ':')),
        )
        if environment not in BSE_STAR_MF_URLS:
            raise BseStarMfError('Environment must be uat or live.')
        if credential is None or not all(_text(getattr(credential, field, '')) for field in ('MemberId', 'UserId', 'Password')):
            raise BseStarMfError(f'BSE Star MF {environment} credentials are not configured completely.')
        if request.query_params.get('preview') == '1':
            safe_payload = {key: value for key, value in envelope.items() if key != 'Password'}
            logger.info('BSE Star MF preview returned: clientcode=%s environment=%s', clientcode, environment)
            return Response({
                'success': True,
                'preview': True,
                'message': 'BSE Star MF payload generated. Provider was not called.',
                'bse_starmf_request_url': request_url,
                'payload': safe_payload,
            })

        response = requests.post(
            BSE_STAR_MF_URLS[environment],
            data=request_body.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        result = _response_json(response)
        response_url = _save_artifact(
            request,
            clientcode,
            'response',
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
        )
        logger.info('BSE Star MF response received: clientcode=%s environment=%s status=%s', clientcode, environment, response.status_code)

        provider_status = _text(result.get('Status')) if isinstance(result, dict) else ''
        success = response.ok and provider_status == '0'
        _set_bse_starmf_push_state(client, success)
        message = _text(result.get('Remarks')) if isinstance(result, dict) else ''
        if not message:
            message = 'BSE Star MF UCC completed successfully.' if success else 'BSE Star MF UCC was rejected.'
        return Response({
            'success': success,
            'message': message,
            'bse_starmf_request_url': request_url,
            'bse_starmf_response_url': response_url,
            'bse_starmf_response': result,
        }, status=status.HTTP_200_OK if success else status.HTTP_502_BAD_GATEWAY)
    except BseStarMfError as exc:
        if client is not None:
            _set_bse_starmf_push_state(client, False)
        logger.warning('BSE Star MF validation failed: clientcode=%s message=%s', clientcode, exc)
        error = {
            'success': False,
            'error': str(exc),
            'message': str(exc),
            'msg': str(exc),
            'errors': [str(exc)],
        }
        try:
            response_url = _save_artifact(request, clientcode, 'response', json.dumps(error, indent=2))
        except OSError:
            logger.exception('Unable to save BSE Star MF error response: clientcode=%s', clientcode)
            response_url = _artifact_url(request, clientcode, 'response')
        return Response({
            **error,
            'request_payload': request_payload,
            'bse_starmf_request_url': request_url,
            'bse_starmf_response': error,
            'bse_starmf_response_url': response_url,
        }, status=status.HTTP_400_BAD_REQUEST)
    except requests.RequestException as exc:
        if client is not None:
            _set_bse_starmf_push_state(client, False)
        logger.exception('BSE Star MF provider connection failed: clientcode=%s', clientcode)
        error_message = f'Unable to connect to BSE Star MF service: {exc}'
        error = {
            'success': False,
            'error': str(exc),
            'message': error_message,
            'msg': error_message,
            'errors': [error_message],
        }
        response_url = _save_artifact(request, clientcode, 'response', json.dumps(error, indent=2))
        return Response({
            **error,
            'request_payload': request_payload,
            'bse_starmf_request_url': request_url,
            'bse_starmf_response': error,
            'bse_starmf_response_url': response_url,
        }, status=status.HTTP_502_BAD_GATEWAY)
    except (DatabaseError, OSError) as exc:
        if client is not None:
            _set_bse_starmf_push_state(client, False)
        logger.exception('BSE Star MF database or file operation failed: clientcode=%s', clientcode)
        error = {
            'success': False,
            'error': str(exc),
            'message': str(exc),
            'msg': str(exc),
            'errors': [str(exc)],
        }
        response_url = _save_artifact(request, clientcode, 'response', json.dumps(error, indent=2))
        return Response({
            **error,
            'request_payload': request_payload,
            'bse_starmf_request_url': request_url,
            'bse_starmf_response': error,
            'bse_starmf_response_url': response_url,
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as exc:
        if client is not None:
            _set_bse_starmf_push_state(client, False)
        logger.exception('Unexpected BSE Star MF failure: clientcode=%s', clientcode)
        error = {
            'success': False,
            'error': str(exc),
            'message': str(exc),
            'msg': str(exc),
            'errors': [str(exc)],
        }
        response_url = _save_artifact(request, clientcode, 'response', json.dumps(error, indent=2))
        return Response({
            **error,
            'request_payload': request_payload,
            'bse_starmf_request_url': request_url,
            'bse_starmf_response': error,
            'bse_starmf_response_url': response_url,
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
