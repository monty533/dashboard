"""Shared provider permission and push-order guards."""

from rest_framework import status
from rest_framework.response import Response


PROVIDER_PERMISSION_FIELDS = {
    'BSE': 'bse_push',
    'BSE STAR MF': 'bsestarmf_push',
    'NSE': 'nse_push',
    'NSDL': 'nsdl_push',
    'CDSL': 'cdsl_push',
    'MCX': 'mcx_push',
    'MSE': 'mse_push',
    'CKYC': 'ckyc_push',
    'KRA': 'kra_push',
}

# Provider dependencies are defined once here so every API endpoint and every
# retry path follows the same order. KRA must run first, NSDL/CDSL follow KRA,
# and NSE/BSE follow either NSDL or CDSL. Other providers are unrestricted.
PROVIDER_PREREQUISITES = {
    'KRA': (),
    'NSDL': ('KRA',),
    'CDSL': ('KRA',),
    'NSE': ('NSDL', 'CDSL'),
    'BSE': ('NSDL', 'CDSL'),
    'BSE STAR MF': (),
    'MCX': (),
    'MSE': (),
    'CKYC': (),
}

PROVIDER_PUSH_AT_FIELDS = {
    'BSE': 'bse_push_at',
    'BSE STAR MF': 'bsestarmf_push_at',
    'NSE': 'nse_push_at',
    'NSDL': 'nsdl_push_at',
    'CDSL': 'cdsl_push_at',
    'MCX': 'mcx_push_at',
    'MSE': 'mse_push_at',
    'CKYC': 'ckyc_push_at',
    'KRA': 'kra_push_at',
}


def is_selected(value):
    return str(value or '').strip().casefold() in {'1', 'true', 'yes', 'y', 'on'}


def is_push_success(value):
    return value is True or str(value).strip().casefold() in {
        '1', 'true', 'success', 'accepted', 'completed',
    }


def provider_is_enabled(client, provider_name):
    """Return whether the provider permission is enabled for this client."""
    permission_field = PROVIDER_PERMISSION_FIELDS.get(provider_name)
    return bool(
        permission_field
        and is_selected(getattr(client, permission_field, None))
    )


def provider_is_complete(client, provider_name):
    """Return whether the provider has a successful push timestamp."""
    timestamp_field = PROVIDER_PUSH_AT_FIELDS.get(provider_name)
    return bool(timestamp_field and getattr(client, timestamp_field, None))


def reject_if_provider_order_blocked(client, provider_name):
    """Block a provider until its required provider push has completed."""
    prerequisites = PROVIDER_PREREQUISITES.get(provider_name, ())
    # NSE and BSE can run after either NSDL or CDSL has completed.
    if provider_name in {'NSE', 'BSE'}:
        enabled_prerequisites = [
            prerequisite
            for prerequisite in prerequisites
            if provider_is_enabled(client, prerequisite)
        ]
        if not enabled_prerequisites:
            return None
        if any(
            provider_is_complete(client, prerequisite)
            for prerequisite in enabled_prerequisites
        ):
            return None
        required_provider = ' or '.join(enabled_prerequisites)
        message = (
            f'{provider_name} push is blocked until either {required_provider} '
            'push is completed successfully.'
        )
        return Response(
            {
                'success': False,
                'status': 'PUSH_ORDER_BLOCKED',
                'push_order_blocked': True,
                'blocked_provider': provider_name,
                'required_providers': enabled_prerequisites,
                'msg': message,
            },
            status=status.HTTP_409_CONFLICT,
        )

    for prerequisite in prerequisites:
        if provider_is_complete(client, prerequisite):
            continue

        message = (
            f'{provider_name} push is blocked until {prerequisite} push '
            'is completed successfully.'
        )
        return Response(
            {
                'success': False,
                'status': 'PUSH_ORDER_BLOCKED',
                'push_order_blocked': True,
                'blocked_provider': provider_name,
                'required_provider': prerequisite,
                'msg': message,
            },
            status=status.HTTP_409_CONFLICT,
        )
    return None


def reject_if_api_not_selected(client, provider_name):
    """Return an error when the provider permission is disabled."""
    permission_field = PROVIDER_PERMISSION_FIELDS.get(provider_name)
    if not permission_field:
        return None

    if is_selected(getattr(client, permission_field, None)):
        return None

    message = (
        f'{provider_name} push is disabled for this client. '
        f'Set {permission_field} to true to enable it.'
    )
    return Response(
        {
            'success': False,
            'api_not_selected': True,
            'msg': message,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def reject_if_already_pushed(client, state_field, provider_name):
    """Return a conflict response only after permission and push timestamp exist."""
    value = getattr(client, state_field, None)
    timestamp_field = state_field.replace('_push', '_push_at', 1)
    push_timestamp = getattr(client, timestamp_field, None)
    if is_push_success(value) and push_timestamp:
        message = f'{provider_name} has already been pushed for this client.'
        return Response(
            {
                'success': False,
                'already_pushed': True,
                'msg': message,
            },
            status=status.HTTP_409_CONFLICT,
        )
    return None
