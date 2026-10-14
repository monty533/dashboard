import html
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils.timezone import get_current_timezone, localtime
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import CdslUpload, UserDetails


logger = logging.getLogger(__name__)


API_CONFIG = (
    ('BSE', 'bse_push', 'bse_push_at', None, None),
    ('BSE STAR MF', 'bsestarmf_push', 'bsestarmf_push_at', None, None),
    ('NSE', 'nse_push', 'nse_push_at', None, None),
    ('NSDL', 'nsdl_push', 'nsdl_push_at', None, None),
    ('CDSL', 'cdsl_push', 'cdsl_push_at', 'cdsl_data', 'response.txt'),
    ('MCX', 'mcx_push', 'mcx_push_at', None, None),
    ('MSE', 'mse_push', 'mse_push_at', 'mse_data', 'mse_response.txt'),
    ('CKYC', 'ckyc_push', 'ckyc_push_at', None, None),
    ('KRA', 'kra_push', 'kra_push_at', None, None),
)
VALID_API_TYPES = {config[0] for config in API_CONFIG}
VALID_STATUSES = {'pending', 'failure', 'success'}
TRANSACTION_TYPE_LABELS = {
    'account_opening': 'Account Opening',
    'segment_addition': 'Segment Addition',
    'modification': 'Modification',
}
VALID_TRANSACTION_TYPES = set(TRANSACTION_TYPE_LABELS)
CLIENT_CODE_PATTERN = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}\Z')
LOG_ARTIFACTS = {
    'BSE': ('bse_data', 'bse_response.txt'),
    'BSE STAR MF': ('bse_star_mf_data', 'bse_starmf_response.txt'),
    'NSE': ('nse_data', 'nse_response.txt'),
    'NSDL': ('nsdl_data', 'nsdl_response.txt'),
    'CDSL': ('cdsl_data', 'response.txt'),
    'MCX': ('mcx_data', 'mcx_response.txt'),
    'MSE': ('mse_data', 'mse_response.txt'),
    'CKYC': ('ckyc_data', 'ckyc_response.txt'),
    'KRA': ('kra_data', 'kra_response.txt'),
}
def _parse_filter_date(value, field_name):
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, f'{field_name} must be a valid date.'


def _push_status(value, push_date=None):
    if value is True or str(value).strip().casefold() in {
        '1', 'true', 'success', 'accepted', 'completed',
    }:
        return 'success'
    if value is False or str(value).strip().casefold() in {'0', 'false', 'failure', 'failed'}:
        if not push_date:
            return 'pending'
        return 'failure'
    return 'pending'


def _artifact_status(api_type, clientcode, directory, filename):
    """Read status/date from an integration response artifact."""
    path = Path(settings.BASE_DIR) / 'static' / directory / clientcode / filename
    if not path.is_file():
        return 'pending', None

    try:
        push_date = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=get_current_timezone(),
        )
        details = json.loads(path.read_text(encoding='utf-8')[:500_000])
    except (OSError, TypeError, ValueError):
        return 'failure', push_date if 'push_date' in locals() else None

    if isinstance(details, dict):
        if 'success' in details:
            return _push_status(details.get('success'), push_date), push_date
        provider_status = details.get('status') or details.get('Status')
        if provider_status is not None:
            return _push_status(provider_status, push_date), push_date

        if api_type == 'NSDL':
            provider_error = details.get('error')
            if provider_error not in (None, '', '0', 0, '200', 200):
                return 'failure', push_date
            return 'success', push_date

        if api_type == 'MCX':
            results = details.get('results')
            if isinstance(results, list) and results:
                has_failure = any(
                    isinstance(item, dict)
                    and (
                        item.get('error_codes')
                        or str(item.get('status', '')).strip().casefold() in {'fail', 'failure', 'failed'}
                    )
                    for item in results
                )
                return ('failure' if has_failure else 'success'), push_date

        if api_type == 'MSE':
            status_response = details.get('status_response')
            if isinstance(status_response, dict):
                provider_status = str(status_response.get('status', '')).strip()
                if provider_status == '2':
                    return 'success', push_date
                if provider_status == '-1':
                    return 'failure', push_date
                if provider_status == '1':
                    return 'pending', push_date

        if api_type == 'KRA':
            if details.get('error_code'):
                return 'failure', push_date
            result_container = details.get('resdtls', details)
            if isinstance(result_container, dict):
                ky_data = result_container.get('KYCDATA', result_container)
                if isinstance(ky_data, list):
                    ky_data = ky_data[0] if ky_data and isinstance(ky_data[0], dict) else {}
                if isinstance(ky_data, dict) and ky_data.get('APP_STATUS'):
                    return ('success' if str(ky_data['APP_STATUS']).strip() == '01' else 'failure'), push_date

    return 'pending', push_date


def _cdsl_status(value):
    normalized = str(value or '').strip().casefold()
    if normalized in {'accepted', 'success', 'completed'}:
        return 'success'
    if normalized in {'rejected', 'failed', 'failure', 'error'}:
        return 'failure'
    return 'pending'


def _provider_status(api_type, permission_value, push_date, clientcode):
    """Treat permission as eligibility and provider artifacts as the result."""
    enabled = permission_value is True or str(permission_value).strip().casefold() in {
        '1', 'true', 'yes', 'y', 'on',
    }
    if not enabled:
        return 'pending', push_date

    artifact_config = LOG_ARTIFACTS.get(api_type)
    if artifact_config:
        artifact_status, artifact_date = _artifact_status(
            api_type,
            clientcode,
            *artifact_config,
        )
        if artifact_date:
            return artifact_status, push_date or artifact_date

    # Successful adapters write *_push_at only after provider success.
    return ('success' if push_date else 'pending'), push_date


def _log_message(details):
    """Extract the most useful provider error for the dashboard log modal."""
    if isinstance(details, str):
        return details.strip() or 'Provider response saved for this failed request.'
    if not isinstance(details, dict):
        return 'Provider response saved for this failed request.'

    raw_response = details.get('raw_response')
    if raw_response:
        # BSE can return an HTML error page instead of JSON. Strip markup so
        # the dashboard modal shows the actual provider message as readable text.
        message = html.unescape(str(raw_response))
        message = re.sub(r'<[^>]*>', ' ', message)
        message = ' '.join(message.split())
        if message:
            return message[:2000]

    response_rows = details.get('ResponceList') or details.get('response')
    if isinstance(response_rows, list):
        for row in response_rows:
            if not isinstance(row, dict):
                continue
            for field_name in (
                'ERRORRESPONSE',
                'error_response',
                'error',
                'error_message',
                'message',
                'msg',
                'Remarks',
                'APP_STATUS_DESC',
                'APP_ERROR_DESC',
            ):
                value = row.get(field_name)
                if value not in (None, '', 0, '0'):
                    return str(value)

    for field_name in (
        'error',
        'error_message',
        'errorDescription',
        'message',
        'msg',
        'Remarks',
        'APP_STATUS_DESC',
        'APP_ERROR_DESC',
    ):
        value = details.get(field_name)
        if value not in (None, '', 0, '0'):
            return str(value)

    for field_name in (
        'provider_response',
        'details',
        'response',
        'resdtls',
        'kra_response',
        'nsdl_response',
    ):
        nested = details.get(field_name)
        if isinstance(nested, (dict, list, str)):
            nested_message = _log_message(nested)
            if nested_message != 'Provider response saved for this failed request.':
                return nested_message

    return 'Provider response saved for this failed request.'


def _display_datetime(value):
    if not value:
        return ''
    return localtime(value).strftime('%Y-%m-%d %H:%M:%S')


def _in_date_range(value, from_date, to_date):
    """Match the selected calendar dates against an API push timestamp."""
    if not from_date and not to_date:
        return True
    if not value:
        return False

    pushed_date = localtime(value).date()
    return not (
        (from_date and pushed_date < from_date)
        or (to_date and pushed_date > to_date)
    )


def _client_summary(rows):
    """Count each client once using failure > pending > success priority."""
    client_statuses = {}
    for row in rows:
        client_key = (row.get('user_id'), row.get('client_code'))
        client_statuses.setdefault(client_key, set()).add(row.get('status'))

    failure_count = sum('failure' in statuses for statuses in client_statuses.values())
    pending_count = sum(
        'failure' not in statuses and 'pending' in statuses
        for statuses in client_statuses.values()
    )
    success_count = sum(
        'failure' not in statuses and 'pending' not in statuses and 'success' in statuses
        for statuses in client_statuses.values()
    )
    return {
        'total_clients': len(client_statuses),
        'success': success_count,
        'failure': failure_count,
        'pending': pending_count,
    }


@api_view(['GET'])
def dashboard_view(request):
    """Return API push rows filtered by push date and dashboard controls."""
    api_type = request.GET.get('api_type', 'ALL').strip().upper()
    status_filter = request.GET.get('status', 'ALL').strip().casefold()
    transaction_type_filter = request.GET.get('transaction_type', '').strip().casefold()
    client_filter = request.GET.get('client_code', '').strip()[:200]
    logger.info(
        'Dashboard request: user_id=%s api_type=%s from=%s to=%s transaction_type=%s status=%s',
        getattr(request.user, 'id', None),
        api_type,
        request.GET.get('from_date', ''),
        request.GET.get('to_date', ''),
        transaction_type_filter or 'all',
        status_filter,
    )

    if api_type not in {'ALL', *VALID_API_TYPES}:
        return Response({'error': 'Invalid API type.'}, status=status.HTTP_400_BAD_REQUEST)
    if status_filter not in {'all', *VALID_STATUSES}:
        return Response({'error': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
    if transaction_type_filter and transaction_type_filter not in VALID_TRANSACTION_TYPES:
        return Response({'error': 'Invalid transaction type.'}, status=status.HTTP_400_BAD_REQUEST)

    from_date, error = _parse_filter_date(request.GET.get('from_date', ''), 'from_date')
    if error:
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
    to_date, error = _parse_filter_date(request.GET.get('to_date', ''), 'to_date')
    if error:
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
    if from_date or to_date:
        if api_type == 'ALL':
            return Response(
                {'error': 'Select one API type when filtering by date.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not from_date or not to_date:
            return Response(
                {'error': 'Both from_date and to_date are required for date filtering.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if from_date and to_date and from_date > to_date:
        return Response(
            {'error': 'from_date cannot be later than to_date.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    selected_api_configs = tuple(
        config for config in API_CONFIG
        if api_type == 'ALL' or config[0] == api_type
    )
    selected_fields = {
        field_name
        for _, state_field, date_field, _, _ in selected_api_configs
        for field_name in (state_field, date_field)
        if field_name
    }
    client_fields = [
        'id',
        'clientcode',
        'aadhaar_name',
        'transaction_type',
        'account_holder_type',
        'user_id',
        'user__profile__company_name',
        *sorted(selected_fields),
    ]
    clients = UserDetails.objects.values(*client_fields)
    if request.user.is_staff or request.user.is_superuser:
        user_id = request.GET.get('user_id')
        clients = clients.filter(user__is_staff=False, user__is_superuser=False)
        if user_id:
            try:
                clients = clients.filter(user_id=int(user_id))
            except (TypeError, ValueError):
                return Response({'error': 'Invalid company.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        clients = clients.filter(user=request.user)

    if client_filter:
        clients = clients.filter(
            Q(clientcode__icontains=client_filter)
            | Q(aadhaar_name__icontains=client_filter)
        )
    if transaction_type_filter:
        clients = clients.filter(transaction_type__iexact=transaction_type_filter)

    client_rows = list(clients)
    latest_cdsl_uploads = {}
    if any(config[0] == 'CDSL' for config in selected_api_configs):
        client_ids = [client['id'] for client in client_rows]
        latest_uploads = CdslUpload.objects.filter(
            client_id__in=client_ids,
        ).values('client_id', 'status', 'created_at').order_by('client_id', '-id')
        for upload in latest_uploads:
            latest_cdsl_uploads.setdefault(upload['client_id'], upload)

    rows = []
    transaction_types = set()
    for client in client_rows:
        transaction_type_value = str(client.get('transaction_type') or '').strip().casefold()
        transaction_type = TRANSACTION_TYPE_LABELS.get(transaction_type_value, transaction_type_value)
        if transaction_type:
            transaction_types.add(transaction_type)

        for current_api_type, state_field, date_field, artifact_dir, artifact_name in selected_api_configs:
            permission_enabled = state_field and (
                client.get(state_field) is True
                or str(client.get(state_field)).strip().casefold() in {
                    '1', 'true', 'yes', 'y', 'on',
                }
            )
            if not permission_enabled:
                continue

            if current_api_type == 'CDSL':
                upload = latest_cdsl_uploads.get(client['id'])
                row_status = _cdsl_status(upload.get('status') if upload else '')
                push_date = upload.get('created_at') if upload else None
            elif state_field:
                push_date = client.get(date_field)
                row_status, push_date = _provider_status(
                    current_api_type,
                    client.get(state_field),
                    push_date,
                    client.get('clientcode') or '',
                )
            else:
                row_status, push_date = _artifact_status(
                    current_api_type,
                    client.get('clientcode') or '',
                    artifact_dir,
                    artifact_name,
                )
            if status_filter != 'all' and status_filter != row_status:
                continue
            # Date filtering is based on this API's own push event. When
            # ALL is selected, each API row is checked with its own timestamp.
            if not _in_date_range(push_date, from_date, to_date):
                continue

            rows.append({
                'id': client['id'],
                'user_id': client['user_id'],
                'client_code': client.get('clientcode') or '',
                'client_name': client.get('aadhaar_name') or '',
                'api_type': current_api_type,
                'transaction_type': transaction_type,
                'status': row_status,
                'account_holder_type': client.get('account_holder_type') or '',
                'push_date': _display_datetime(push_date),
                'company_name': client.get('user__profile__company_name') or '',
            })

    rows.sort(key=lambda row: row['push_date'] or '0000-00-00 00:00:00', reverse=True)

    try:
        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(1000, max(1, int(request.GET.get('page_size', 25))))
    except (TypeError, ValueError):
        page, page_size = 1, 25

    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]

    logger.info(
        'Dashboard result: user_id=%s api_type=%s total=%s page=%s',
        getattr(request.user, 'id', None),
        api_type,
        total,
        page,
    )
    summary = _client_summary(rows)
    logger.info(
        'Dashboard summary: user_id=%s clients=%s success=%s failure=%s pending=%s',
        getattr(request.user, 'id', None),
        summary['total_clients'],
        summary['success'],
        summary['failure'],
        summary['pending'],
    )
    return Response({
        'rows': page_rows,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'transaction_types': sorted(transaction_types, key=str.casefold),
        'summary': summary,
    })


@api_view(['GET'])
def dashboard_log_view(request):
    """Return the saved provider response/error for one failed dashboard row."""
    api_type = request.GET.get('api_type', '').strip().upper()
    if api_type not in LOG_ARTIFACTS:
        logger.warning('Dashboard log requested with invalid API type: api_type=%s', api_type)
        return Response({'error': 'Invalid API type.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client_id = int(request.GET.get('client_id', ''))
    except (TypeError, ValueError):
        return Response({'error': 'Invalid client.'}, status=status.HTTP_400_BAD_REQUEST)

    clients = UserDetails.objects.select_related('user').filter(pk=client_id)
    if request.user.is_staff or request.user.is_superuser:
        clients = clients.filter(user__is_staff=False, user__is_superuser=False)
        user_id = request.GET.get('user_id')
        if user_id:
            try:
                clients = clients.filter(user_id=int(user_id))
            except (TypeError, ValueError):
                return Response({'error': 'Invalid company.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        clients = clients.filter(user=request.user)

    client = clients.first()
    if client is None:
        return Response({'error': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not CLIENT_CODE_PATTERN.fullmatch(client.clientcode or ''):
        return Response({'error': 'Invalid client code.'}, status=status.HTTP_400_BAD_REQUEST)

    directory, filename = LOG_ARTIFACTS[api_type]
    log_path = Path(settings.BASE_DIR) / 'static' / directory / client.clientcode / filename
    if not log_path.is_file():
        logger.warning(
            'Dashboard log not found: client_id=%s api_type=%s',
            client_id,
            api_type,
        )
        return Response(
            {'error': 'No saved log is available for this client/API.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        raw_log = log_path.read_text(encoding='utf-8')
    except OSError:
        return Response({'error': 'The saved log could not be read.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Keep the modal responsive even if a provider returns a very large body.
    raw_log = raw_log[:500_000]
    try:
        details = json.loads(raw_log)
    except (TypeError, ValueError):
        details = raw_log

    message = _log_message(details)

    logger.info(
        'Dashboard log loaded: client_id=%s api_type=%s',
        client_id,
        api_type,
    )
    return Response({
        'client_code': client.clientcode,
        'api_type': api_type,
        'file_name': f'{directory}/{client.clientcode}/{filename}',
        'message': str(message),
        'details': details,
        'raw_log': raw_log,
    })
